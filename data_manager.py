import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
import time
import re
from datetime import datetime

# ==============================================================================
# ⚙️ 設定區
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit"
# ==============================================================================

# --- 核心工具函式 ---
def safe_float(value):
    if pd.isna(value) or value == '' or value is None: return 0.0
    try:
        s = str(value).strip()
        s = s.replace(',', '').replace('$', '').replace('¥', '').replace('%', '')
        s = s.replace('萬', '0000').replace('(', '-').replace(')', '')
        return float(s)
    except: return 0.0

def fmt_money(value):
    val = safe_float(value)
    return f"{val:,.2f}" if val != 0 else "0.00"

def fmt_int(value):
    val = safe_float(value)
    return f"{val:,.0f}" if val != 0 else "0"

def fmt_date(value):
    try: return pd.to_datetime(value).strftime('%Y-%m-%d')
    except: return str(value)

def fmt_pct(value):
    val = safe_float(value)
    if val == 0: return "0.00%"
    if abs(val) <= 5.0:
        return f"{val*100:.2f}%"
    else:
        return f"{val:.2f}%"

def fuzzy_get(df, keyword):
    """模糊搜尋 DataFrame 的索引，回傳第一個匹配的值"""
    for idx in df.index:
        if keyword in str(idx):
            return df.loc[idx].iloc[0] 
    return None

def find_col(columns, keyword):
    """在欄位列表中模糊搜尋包含關鍵字的欄位名稱"""
    return next((c for c in columns if keyword in str(c)), None)

# --- 連線與資料讀取 ---
def get_gsheet_connection():
    try:
        if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
            st.error("❌ Secrets 設定錯誤：找不到 [connections.gsheets]。請檢查 .streamlit/secrets.toml")
            return None, None
            
        secrets = dict(st.secrets["connections"]["gsheets"])
        if "private_key" in secrets:
            secrets["private_key"] = secrets["private_key"].replace('\\n', '\n')
            
        gc = gspread.service_account_from_dict(secrets)
        sh = gc.open_by_url(SHEET_URL)
        return gc, sh
    except Exception as e:
        st.error(f"❌ 連線錯誤: {e}")
        return None, None

@st.cache_data(ttl=300) 
def load_data(sheet_name): 
    max_retries = 3
    for attempt in range(max_retries):
        with st.spinner(f"讀取: {sheet_name}..."):
            try:
                gc, sh = get_gsheet_connection() 
                if not sh: return pd.DataFrame()
                
                try:
                    ws = sh.worksheet(sheet_name) 
                    data = ws.get_all_values()
                except gspread.exceptions.WorksheetNotFound:
                    return pd.DataFrame()
                    
                if not data: return pd.DataFrame()
                
                headers = [str(h).strip() for h in data[0]]
                df = pd.DataFrame(data[1:], columns=headers)
                
                # 處理重複欄位名稱
                if len(df.columns) != len(set(df.columns)):
                    cols = []
                    count = {}
                    for c in df.columns:
                        n = "Unnamed" if not c else c
                        if n in count: count[n]+=1; cols.append(f"{n}_{count[n]}")
                        else: count[n]=0; cols.append(n)
                    df.columns = cols
                return df
                
            except Exception as e:
                time.sleep(2)
    return pd.DataFrame()

@st.cache_data(ttl=60) 
def fetch_current_prices(tickers):
    if not tickers: return {}
    ticker_map = {}
    query_tickers = []
    
    for t in tickers:
        raw_t = str(t).strip()
        if not raw_t: continue
        if raw_t.isdigit(): y_t = f"{raw_t}.TW"
        else: y_t = raw_t
        ticker_map[y_t] = raw_t
        query_tickers.append(y_t)
    
    res = {}
    try:
        data = yf.download(query_tickers, period='1d', interval='1d', progress=False)
        if data.empty: return {}
        try: closes = data['Close']
        except: return {}
        if closes.empty: return {}
        last_row = closes.iloc[-1]
        
        if len(query_tickers) == 1:
            val = last_row
            if hasattr(val, 'item'): val = val.item()
            res[ticker_map[query_tickers[0]]] = round(float(val), 2)
        else:
            for y_t, original_t in ticker_map.items():
                try:
                    val = last_row.get(y_t)
                    if pd.notna(val):
                         if hasattr(val, 'item'): val = val.item()
                         res[original_t] = round(float(val), 2)
                except: pass
        return res
    except: return {}

def write_prices_to_sheet(df_A, updates):
    _, sh = get_gsheet_connection()
    if not sh: return False
    try:
        ws = sh.worksheet('表A_持股總表')
        vals = []
        for _, row in df_A.iterrows():
            t = str(row.get('股票','')).strip()
            p = updates.get(t)
            if p: vals.append([p]) 
            else: vals.append([''])
        if vals: ws.update(f'E2:E{2+len(vals)-1}', vals, value_input_option='USER_ENTERED')
        return True
    except: return False

# --- 文字日報生成函式 ---
def generate_daily_report(df_A, df_C, df_D, df_E, df_F, df_H, live_prices_dict):
    """
    生成文字日報
    注意：live_prices_dict 需由外部傳入 st.session_state['live_prices']
    """
    lines = []
    today = datetime.now().strftime('%Y/%m/%d')
    lines.append(f"[日期] {today}\n")

    # --- 表C 總覽 ---
    lines.append("[表C]")
    if not df_C.empty:
        try:
            df_c = df_C.copy()
            first_col = df_c.columns[0]
            df_c[first_col] = df_c[first_col].astype(str).str.strip()
            df_c.set_index(first_col, inplace=True)
            col = df_c.columns[0]
            
            items = {
                '股票市值': '股票市值', 
                '現金': '現金', 
                '質押借款餘額': '質押借款餘額', 
                '總資產市值': '總資產市值', 
                '實質NAV': '實質NAV', 
                '質押率': '質押率',
                '曝險指標 E': '曝險指標 E',
                '槓桿倍數β': '曝險指標 E', 
                'β風險燈號': 'β風險燈號',
                'E風險燈號': 'E風險燈號', 
                '短期財務目標': '短期財務目標', 
                '短期財務目標差距': '目標差距',
                '達成進度': '達成進度',
                '槓桿密度比LDR': 'LDR',
                'LDR燈號': 'LDR燈號'
            }
            
            for key, label in items.items():
                if key in df_c.index:
                    val = df_c.loc[key, col]
                    val_str = str(val)
                    if key in ['達成進度', '槓桿倍數β', '曝險指標 E', '質押率', '槓桿密度比LDR']:
                        if isinstance(val, str) and '%' in val:
                             val_str = val
                        else:
                             val_str = fmt_pct(val)
                    elif key in ['股票市值', '現金', '質押借款餘額', '總資產市值', '實質NAV', '短期財務目標', '短期財務目標差距']:
                          val_str = fmt_int(val)
                    lines.append(f"{label}：{val_str}")
        except Exception as e:
            lines.append(f"讀取表C錯誤: {e}")
    else:
        lines.append("無數據")
    
    # --- 表H 每日判斷 ---
    lines.append("\n[表H_每日判斷]")
    if not df_H.empty:
        try:
            df_h = df_H.copy()
            latest = df_h.iloc[-1]
            
            col_ldr = find_col(df_h.columns, 'LDR')
            col_risk = find_col(df_h.columns, '風險')
            col_pledge = find_col(df_h.columns, '質押')
            col_unwind = find_col(df_h.columns, '拆倉')
            col_fw = find_col(df_h.columns, '飛輪')
            col_cmd = find_col(df_h.columns, '指令')

            ldr = str(latest.get(col_ldr, 'N/A')) if col_ldr else 'N/A'
            risk = str(latest.get(col_risk, 'N/A')) if col_risk else 'N/A'
            pledge = fmt_pct(latest.get(col_pledge, 0)) if col_pledge else '0%'
            unwind = fmt_pct(latest.get(col_unwind, 0)) if col_unwind else '0%'
            flywheel = str(latest.get(col_fw, 'N/A')) if col_fw else 'N/A'
            
            cmd_val = str(latest.get(col_cmd, 'N/A')) if col_cmd else 'N/A'
            cmd = re.sub(r"【Debug.*?】", "", cmd_val, flags=re.DOTALL).strip()
            
            lines.append(f"LDR：{ldr}")
            lines.append(f"風險等級：{risk}")
            lines.append(f"質押率：{pledge}")
            lines.append(f"建議拆倉：{unwind}")
            lines.append(f"飛輪階段：{flywheel}")
            lines.append(f"指令：{cmd}")
        except: lines.append("表H解析錯誤")

    # --- 表A 持股 ---
    lines.append("\n[表A]")
    if not df_A.empty:
        for _, row in df_A.iterrows():
            ticker = str(row.get('股票', '')).strip()
            name = str(row.get('股票名稱', '')) 
            qty = fmt_int(row.get('持有數量（股）', 0)) + "股"
            avg = "均價" + fmt_money(row.get('平均成本', 0))
            
            # 使用傳入的 live_prices_dict
            live_p = live_prices_dict.get(ticker)
            close_val = 0.0
            
            # 修正順序：表A 收盤價 (手動最優先) > 表A 即時收盤價 > API 價格 > 成交價
            price_candidates = [
                row.get('收盤價'),     # 最高優先 (User 手動 key)
                row.get('即時收盤價'), # Google Finance
                live_p,               # Yahoo Finance API
                row.get('成交價')      # 最後備援
            ]
            for p in price_candidates:
                v = safe_float(p)
                if v > 0:
                    close_val = v
                    break
            
            close = "收盤" + f"{close_val:,.2f}"
            mkt_val = safe_float(row.get('持有數量（股）', 0)) * close_val
            mkt = "市值" + f"{mkt_val:,.0f}"
            note = str(row.get('備註', '')).strip()
            
            line = f"{ticker} {name}  {qty}  {avg}  {close}  {mkt}  {note}"
            lines.append(line.strip())

    # --- 表F 最近3日 ---
    lines.append("\n[表F_最近3日]")
    if not df_F.empty:
        try:
            df_f = df_F.copy()
            date_col = next((c for c in df_f.columns if '日期' in c), None)
            if date_col:
                df_f['dt'] = pd.to_datetime(df_f[date_col], errors='coerce')
                unique_dates = sorted(df_f['dt'].dt.date.dropna().unique(), reverse=True)[:3]
                last_3 = df_f[df_f['dt'].dt.date.isin(unique_dates)].sort_values('dt', ascending=True)
                
                for _, row in last_3.iterrows():
                    d = fmt_date(row[date_col])
                    stk_v = "股票市值" + fmt_int(row.get('股票市值', 0))
                    tot = "總資產" + fmt_int(row.get('總資產', 0)) 
                    cash = "現金" + fmt_int(row.get('現金', 0))
                    chg_val = safe_float(row.get('當日淨變動', 0))
                    chg = "當日淨變動" + fmt_int(chg_val)
                    nav = "NAV" + fmt_int(row.get('實質NAV', 0))
                    
                    beta_raw = row.get('曝險指標 E', row.get('槓桿倍數β', 0))
                    beta_val = safe_float(beta_raw)
                    
                    if beta_val <= 5.0: beta = f"E{beta_val*100:.2f}%"
                    else: beta = f"E{beta_val:.2f}%"
                    
                    lines.append(f"{d} {stk_v} {tot} {cash} {chg} {nav} {beta}")
            else:
                lines.append("表F無日期欄位")
        except: lines.append("表F解析錯誤")

    # --- 表D 近3日交易 ---
    lines.append("\n[表D_近3日交易]")
    if not df_D.empty:
        try:
            df_d = df_D.copy()
            date_col = next((c for c in df_d.columns if '日期' in c), None)
            if date_col:
                df_d['dt'] = pd.to_datetime(df_d[date_col], errors='coerce')
                unique_dates = sorted(df_d['dt'].dt.date.dropna().unique(), reverse=True)[:3]
                last_d = df_d[df_d['dt'].dt.date.isin(unique_dates)].sort_values('dt', ascending=True)
                
                for _, row in last_d.iterrows():
                    d = fmt_date(row[date_col])
                    item = str(row.get('用途／股票', ''))
                    act = str(row.get('動作', ''))
                    amt_raw = safe_float(row.get('淨收／支出', 0))
                    amt_sign = f"+{fmt_int(amt_raw)}" if amt_raw > 0 else fmt_int(amt_raw)
                    amt_str = f"金額{amt_sign}"
                    qty_val = safe_float(row.get('數量', 0))
                    qty = f"{fmt_int(qty_val)}股" if qty_val > 0 else ""
                    price_val = safe_float(row.get('成交價', 0))
                    price = fmt_money(price_val) if price_val > 0 else ""
                    note = str(row.get('備註', '')).strip()
                    note_str = f"備註：{note}" if note else ""
                    line = f"{d} {item} {act} {qty} {price} {amt_str} {note_str}"
                    lines.append(re.sub(' +', ' ', line).strip())
            else:
                lines.append("表D無日期欄位")
        except: lines.append("表D解析錯誤")

    # --- 表E 近3日已實現損益 ---
    lines.append("\n[表E_近3日已實現損益]")
    if not df_E.empty:
        try:
            df_e = df_E.copy()
            d_col = next((c for c in df_e.columns if '日期' in c), None)
            if d_col:
                df_e['dt'] = pd.to_datetime(df_e[d_col], errors='coerce')
                unique_dates = sorted(df_e['dt'].dt.date.dropna().unique(), reverse=True)[:3]
                last_e = df_e[df_e['dt'].dt.date.isin(unique_dates)].sort_values('dt', ascending=True)
                
                for _, row in last_e.iterrows():
                    d = fmt_date(row[d_col])
                    stk = str(row.get('股票', ''))
                    pnl_raw = safe_float(row.get('已實現損益', 0))
                    pnl_sign = f"+{fmt_int(pnl_raw)}" if pnl_raw > 0 else fmt_int(pnl_raw)
                    pnl_str = f"損益{pnl_sign}"
                    qty = fmt_int(row.get('成交股數', 0)) + "股"
                    note = str(row.get('備註', '')).strip()
                    lines.append(f"{d} {stk} {qty} {pnl_str} {note}")
            else:
                lines.append("無日期欄位可排序")
        except: lines.append("表E解析錯誤")

    return "\n".join(lines)
