import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import yfinance as yf
import gspread
import time
import re
import numpy as np

# ==============================================================================
# ⚙️ 設定區：請將您的 Google Sheet 網址填入下方
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit"
# ==============================================================================

# 設置頁面配置
st.set_page_config(layout="wide", page_title="投資組合儀表板")

# 注入 CSS
st.markdown("""
<style>
/* 1. 調整頁面頂部留白 */
.block-container {
    padding-top: 5rem;
    padding-bottom: 2rem;
}

html, body, [class*="stApp"] { font-size: 16px; }
h1 { font-size: 2.2em; margin-bottom: 0.5rem; }
h2 { font-size: 1.6em; padding-top: 0.5rem; }
h3 { font-size: 1.4em; }

/* 表格設定：隱藏表頭 (針對核心資產優化) */
[data-testid="stDataFrame"] thead {
    display: none;
}

/* 側邊欄按鈕樣式 */
div[data-testid="stSidebar"] .stButton button {
    width: 100%; height: 45px; margin-bottom: 10px; border: 1px solid #ccc;
}

/* 進度條顏色 */
.stProgress > div > div > div > div {
    background-color: #007bff;
}

/* 自訂指標卡片樣式 (用於曝險指標優化) */
.custom-metric-card {
    background-color: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    padding: 12px;
    text-align: center;
    height: 100%; /* 嘗試填滿高度 */
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.metric-label {
    font-size: 0.9em;
    color: #6c757d;
    margin-bottom: 4px;
}
.metric-value {
    font-size: 2.0em; /* 稍微加大數值 */
    font-weight: bold;
    color: #212529;
    line-height: 1.1;
}
.metric-badge {
    display: block; /* 改為區塊元素以滿版 */
    width: 100%;    /* 設定寬度為 100% */
    padding: 6px 0; /* 增加垂直 padding */
    border-radius: 6px;
    color: white;
    font-size: 1.1em; /* 加大字體 */
    font-weight: bold;
    margin-bottom: 10px; /* 增加下方間距 */
}

/* 心態提醒卡片樣式 (調整為填滿) */
.mindset-card {
    background-color: #e8f4f8; /* 淺藍色底 */
    border-left: 5px solid #17a2b8; /* 左側藍色線條 */
    padding: 15px;
    border-radius: 5px;
    margin-top: 15px; /* 與上方卡片保持距離 */
    color: #0f5132;
    font-size: 1.0em;
    display: flex;
    align-items: center;
    width: 100%;
}
</style>
""", unsafe_allow_html=True)

if 'live_prices' not in st.session_state:
    st.session_state['live_prices'] = {}

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
            # 回傳該列的第一欄數據
            return df.loc[idx].iloc[0] 
    return None

# --- 文字日報生成函式 ---
def generate_daily_report(df_A, df_C, df_D, df_E, df_F, df_H):
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
            date_col = next((c for c in df_h.columns if '日期' in c), None)
            if date_col:
                df_h['dt'] = pd.to_datetime(df_h[date_col], errors='coerce')
                latest = df_h.sort_values('dt', ascending=False).iloc[0]
                
                ldr = str(latest.get('LDR', 'N/A'))
                risk = str(latest.get('今日風險等級', 'N/A'))
                pledge = fmt_pct(latest.get('質押率', 0))
                unwind = fmt_pct(latest.get('建議拆倉比例', 0))
                
                fw_col = next((c for c in df_h.columns if '飛輪' in c), None)
                flywheel = str(latest.get(fw_col, 'N/A')) if fw_col else 'N/A'
                
                cmd = str(latest.get('今日指令', 'N/A'))
                cmd = re.sub(r"【Debug.*?】", "", cmd, flags=re.DOTALL).strip()
                
                lines.append(f"LDR：{ldr}")
                lines.append(f"風險等級：{risk}")
                lines.append(f"質押率：{pledge}")
                lines.append(f"建議拆倉：{unwind}")
                lines.append(f"飛輪階段：{flywheel}")
                lines.append(f"指令：{cmd}")
            else:
                 lines.append("表H無日期欄位")
        except: lines.append("表H解析錯誤")

    # --- 表A 持股 ---
    lines.append("\n[表A]")
    if not df_A.empty:
        for _, row in df_A.iterrows():
            ticker = str(row.get('股票', '')).strip()
            name = str(row.get('股票名稱', '')) 
            qty = fmt_int(row.get('持有數量（股）', 0)) + "股"
            avg = "均價" + fmt_money(row.get('平均成本', 0))
            
            live_p = st.session_state['live_prices'].get(ticker)
            close_val = 0.0
            price_candidates = [
                live_p, 
                row.get('收盤價'), 
                row.get('即時收盤價'), 
                row.get('成交價')
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

# --- 連線工具 (強化版) ---
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

@st.cache_data(ttl=3600) 
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

# === 主程式 ===

# 載入所有資料 (先讀取資料才能決定標題日期)
df_A = load_data('表A_持股總表')
df_B = load_data('表B_持股比例')
df_C = load_data('表C_總覽')
df_D = load_data('表D_現金流')
df_E = load_data('表E_已實現損益')
df_F = load_data('表F_每日淨值')
df_G = load_data('表G_財富藍圖') 
df_H = load_data('表H_每日判斷')
df_Market = load_data('Market')
df_Global = load_data('Global')

# 決定標題日期字串
date_str = ""
if not df_F.empty:
    try:
        # 尋找包含「日期」的欄位
        d_col = next((c for c in df_F.columns if '日期' in c), None)
        if d_col:
            dt_series = pd.to_datetime(df_F[d_col], errors='coerce')
            latest_dt = dt_series.max()
            if pd.notna(latest_dt):
                date_str = f"-{latest_dt.year}年{latest_dt.month}月{latest_dt.day}日"
    except:
        pass

st.title(f'💰 投資組合儀表板{date_str}')

lev = 0.0

st.sidebar.header("🎯 數據管理")
if st.sidebar.button("🔄 重新載入資料"):
    load_data.clear()
    st.rerun()

if st.sidebar.button("💾 更新股價至 Google Sheets", type="primary"):
    if not df_A.empty and '股票' in df_A.columns:
        tickers = [t for t in df_A['股票'].unique() if str(t).strip()]
        st.toast(f"正在更新 {len(tickers)} 檔股價...", icon="⏳")
        updates = fetch_current_prices(tickers)
        st.session_state['live_prices'] = updates
        if updates:
            success = write_prices_to_sheet(df_A, updates)
            if success:
                st.sidebar.success(f"成功更新 {len(updates)} 檔股價！")
                time.sleep(1)
                load_data.clear()
                st.rerun()
        else:
            st.sidebar.warning("未能取得任何股價，請檢查代碼或網路。")

st.sidebar.markdown("---")
st.sidebar.subheader("📋 匯出功能")
if st.sidebar.button("產生文字日報"):
    report_text = generate_daily_report(df_A, df_C, df_D, df_E, df_F, df_H)
    st.sidebar.markdown("請點擊下方代碼區塊右上角的 **複製按鈕**：")
    st.sidebar.code(report_text, language='text')

st.sidebar.markdown("---")
with st.sidebar.expander("🛠️ 連線狀態檢查"):
    st.write(f"目前設定的 Sheet URL: `{SHEET_URL}`")
    if "connections" in st.secrets: st.success("✅ Secrets 設定已偵測到")
    else: st.error("❌ 找不到 Secrets 設定")

st.sidebar.markdown("---")

# --- 新增：心態提醒區塊 ---
if not df_H.empty:
    try:
        # 先轉換日期以取得最新資料
        df_h_temp = df_H.copy()
        date_col = next((c for c in df_h_temp.columns if '日期' in c), None)
        if date_col:
            df_h_temp['dt'] = pd.to_datetime(df_h_temp[date_col], errors='coerce')
            latest_row = df_h_temp.sort_values('dt', ascending=False).iloc[0]
            
            # 優先搜尋包含「心態」或「提醒」的欄位
            mindset_col = next((c for c in df_h_temp.columns if '心態' in str(c) or '提醒' in str(c)), None)
            
            # 如果找不到，嘗試使用第 11 欄 (索引 10, 即 K 欄)
            if not mindset_col and len(df_h_temp.columns) > 10:
                mindset_col = df_h_temp.columns[10]
            
            if mindset_col:
                mindset_text = str(latest_row.get(mindset_col, '')).strip()
                if mindset_text:
                    st.markdown(f"""
                    <div class="mindset-card">
                        💡 <b>心態提醒：</b> {mindset_text}
                    </div>
                    """, unsafe_allow_html=True)
    except Exception as e:
        pass # 失敗則不顯示，保持版面乾淨

# 1. 投資總覽
st.header('1. 投資總覽')
if not df_C.empty:
    df_c = df_C.copy()
    first_col = df_c.columns[0]
    df_c[first_col] = df_c[first_col].astype(str).str.strip()
    df_c.set_index(first_col, inplace=True)
    col_val = df_c.columns[0]
    
    risk = str(df_c.loc['E風險燈號', col_val]) if 'E風險燈號' in df_c.index else str(df_c.loc['β風險燈號', col_val]) if 'β風險燈號' in df_c.index else '未知'
    risk_txt = re.sub(r'\s+', '', risk)
    val_lev = df_c.loc['曝險指標 E', col_val] if '曝險指標 E' in df_c.index else df_c.loc['槓桿倍數β', col_val] if '槓桿倍數β' in df_c.index else 0
    lev = safe_float(val_lev)

    style = {'e':'❓', 'bg':'#6c757d', 't':'white'}
    if '安全' in risk_txt: style = {'e':'✅', 'bg':'#28a745', 't':'white'}
    elif '警戒' in risk_txt or '警示' in risk_txt: style = {'e':'⚠️', 'bg':'#ffc107', 't':'black'}
    elif '危險' in risk_txt: style = {'e':'🚨', 'bg':'#dc3545', 't':'white'}

    # Layout: 2 Columns [1, 3] -> Left: Table, Right: Cards & Mindset
    c_left, c_right = st.columns([1, 3])
    
    # Left Column: Core Assets Table
    with c_left:
        st.subheader('核心資產')
        mask = ~df_c.index.isin([
            'β風險燈號', 'E風險燈號', '槓桿倍數β', '曝險指標 E',
            '短期財務目標', '短期財務目標差距', '達成進度', 
            'LDR', 'LDR燈號', '槓桿密度比LDR', '質押率', '質押率燈號',
            '頭期款', '頭期款目標', '房屋準備度R', '目標房屋準備度R', '預估買房年份'
        ])
        df_show = df_c[mask].reset_index().iloc[:, :2]
        df_show.columns = ['項目', '數值'] 
        st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Right Column: Cards & Mindset
    with c_right:
        # Top Row of Right Column: 3 Cards
        rc1, rc2, rc3 = st.columns(3)
        
        # Card 1: Exposure
        with rc1:
            st.subheader('曝險指標')
            st.markdown(f"""
            <div class='custom-metric-card'>
                <div class='metric-badge' style='background-color: {style['bg']}; color: {style['t']};'>
                    {style['e']} {risk}
                </div>
                <div class='metric-label'>曝險倍數</div>
                <div class='metric-value'>{lev:.2f}</div>
            </div>
            """, unsafe_allow_html=True)

        # Card 2: Short Term Goal
        with rc2:
            st.subheader('短期目標')
            try:
                target = safe_float(df_c.loc['短期財務目標', col_val]) if '短期財務目標' in df_c.index else 0
                gap = safe_float(df_c.loc['短期財務目標差距', col_val]) if '短期財務目標差距' in df_c.index else 0
                pct = 0.0
                curr = 0
                if target > 0:
                    curr = target - gap
                    pct = max(0.0, min(1.0, curr/target))
                
                st.markdown(f"""
                <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:10px; border:1px solid #e9ecef; height: 100%; display: flex; flex-direction: column; justify-content: center;">
                    <div style="font-size:1.0em; color:#6c757d; margin-bottom:5px;">達成進度</div>
                    <div style="font-size:2.2em; font-weight:bold; color:#007bff; line-height:1.1;">
                        {pct*100:.1f}%
                    </div>
                    <div style="margin-top:8px; font-size:0.85em; display:flex; justify-content:space-between; color:#495057;">
                        <span>目標: <b>{fmt_int(target)}</b></span>
                    </div>
                     <div style="text-align:right; font-size:0.8em; color:#dc3545; margin-top:2px;">
                        (差 {fmt_int(gap)})
                    </div>
                </div>
                """, unsafe_allow_html=True)
            except: pass

        # Card 3: Buying Plan
        with rc3:
            st.subheader('買房計畫')
            try:
                dp_target = 0
                if '頭期款目標' in df_c.index: dp_target = safe_float(df_c.loc['頭期款目標', col_val])
                elif '頭期款' in df_c.index: dp_target = safe_float(df_c.loc['頭期款', col_val])
                
                r_val_raw = None
                if '目標房屋準備度R' in df_c.index: r_val_raw = df_c.loc['目標房屋準備度R', col_val]
                elif '房屋準備度R' in df_c.index: r_val_raw = df_c.loc['房屋準備度R', col_val]
                    
                est_year = "N/A"
                if '預估買房年份' in df_c.index: est_year = str(df_c.loc['預估買房年份', col_val])
                
                r_display = "N/A"
                if r_val_raw is not None:
                    if isinstance(r_val_raw, str) and '%' in r_val_raw: r_display = r_val_raw
                    else:
                        r_float = safe_float(r_val_raw)
                        if r_float != 0: 
                            if abs(r_float) <= 5.0: r_display = f"{r_float*100:.2f}%"
                            else: r_display = f"{r_float:.2f}%"
                        else: r_display = str(r_val_raw)

                st.markdown(f"""
                <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:10px; border:1px solid #e9ecef; height: 100%; display: flex; flex-direction: column; justify-content: center;">
                    <div style="font-size:1.0em; color:#6c757d; margin-bottom:5px;">房屋準備度 R</div>
                    <div style="font-size:2.2em; font-weight:bold; color:#007bff; line-height:1.1;">
                        {r_display}
                    </div>
                    <div style="margin-top:8px; font-size:0.85em; display:flex; justify-content:space-between; color:#495057;">
                        <span>頭期款: <b>{fmt_int(dp_target)}</b></span>
                    </div>
                     <div style="text-align:right; font-size:0.8em; color:#6c757d; margin-top:2px;">
                        (預估 {est_year} 年)
                    </div>
                </div>
                """, unsafe_allow_html=True)
            except: st.error("資料讀取錯誤")
            
        # Bottom of Right Column: Mindset Reminder
        if not df_H.empty:
            try:
                df_h_temp = df_H.copy()
                date_col = next((c for c in df_h_temp.columns if '日期' in c), None)
                if date_col:
                    df_h_temp['dt'] = pd.to_datetime(df_h_temp[date_col], errors='coerce')
                    latest_row = df_h_temp.sort_values('dt', ascending=False).iloc[0]
                    mindset_col = next((c for c in df_h_temp.columns if '心態' in str(c) or '提醒' in str(c)), None)
                    if not mindset_col and len(df_h_temp.columns) > 10: mindset_col = df_h_temp.columns[10]
                    if mindset_col:
                        mindset_text = str(latest_row.get(mindset_col, '')).strip()
                        if mindset_text:
                            st.markdown(f"""
                            <div class="mindset-card">
                                💡 <b>心態提醒：</b> {mindset_text}
                            </div>
                            """, unsafe_allow_html=True)
            except: pass

    # ... (Rest of the app remains same: Daily Judgment, Holdings, Transactions, Wealth Blueprint)
    
    st.subheader('📅 今日判斷 & 市場狀態')

    if not df_H.empty:
        try:
            df_h = df_H.copy()
            date_col = next((c for c in df_h.columns if '日期' in c), None)
            if date_col:
                df_h['dt'] = pd.to_datetime(df_h[date_col], errors='coerce')
                latest = df_h.sort_values('dt', ascending=False).iloc[0]
                
                ldr_raw = str(latest.get('LDR', 'N/A'))
                risk_today = str(latest.get('今日風險等級', 'N/A'))
                cmd = str(latest.get('今日指令', 'N/A'))
                cmd = re.sub(r"【Debug.*?】", "", cmd, flags=re.DOTALL).strip()
                market_pos = str(latest.get('盤勢位置', 'N/A'))
                
                ldr_val_num = safe_float(ldr_raw)
                ldr_ratio = ldr_val_num / 100.0 if ldr_val_num > 5 else ldr_val_num
                e_ratio = lev / 100.0 if lev > 5 else lev 
                
                if e_ratio < 0.95: safe_l, hot_l = 1.05, 1.08
                elif e_ratio < 1.05: safe_l, hot_l = 1.03, 1.06
                else: safe_l, hot_l = 1.01, 1.03
                
                if ldr_ratio <= 1.0: ldr_status_txt, ldr_color = "黃金結構", "#28a745"
                elif ldr_ratio <= safe_l: ldr_status_txt, ldr_color = "偏熱", "#ffc107"
                elif ldr_ratio <= hot_l: ldr_status_txt, ldr_color = "過熱", "#fd7e14"
                else: ldr_status_txt, ldr_color = "危險", "#dc3545"
                
                ldr_display = f"{ldr_val_num:.2f}%<div style='font-size: 1rem; line-height: 1.0; margin-top: 2px;'>{ldr_status_txt}</div>"

                raw_pledge = safe_float(latest.get('質押率', 0))
                pledge_val = raw_pledge * 100 if abs(raw_pledge) <= 5.0 else raw_pledge
                
                sheet_pledge_status = ""
                if not df_C.empty:
                     p_status_raw = fuzzy_get(df_C.set_index(df_C.columns[0]), '質押率燈號')
                     if p_status_raw: sheet_pledge_status = str(p_status_raw).strip()

                if sheet_pledge_status:
                     p_status = sheet_pledge_status
                     if "安全" in p_status: p_color = "#28a745"
                     elif "謹慎" in p_status: p_color = "#17a2b8"
                     elif "高警戒" in p_status: p_color = "#fd7e14"
                     elif "警戒" in p_status: p_color = "#ffc107"
                     elif "危險" in p_status: p_color = "#dc3545"
                     else: p_color = "black"
                else:
                    if pledge_val < 30: p_status, p_color = "安全（絕對安全區）", "#28a745"
                    elif pledge_val < 35: p_status, p_color = "謹慎可開火區", "#17a2b8"
                    elif pledge_val < 40: p_status, p_color = "警戒（火力鎖定區）", "#ffc107"
                    elif pledge_val < 45: p_status, p_color = "高警戒", "#fd7e14"
                    else: p_status, p_color = "危險", "#dc3545"
                
                pledge_display = f"{pledge_val:.2f}%<div style='font-size: 1rem; line-height: 1.0; margin-top: 2px; white-space: normal; word-break: break-word;'>{p_status}</div>"
                unwind_rate = fmt_pct(latest.get('建議拆倉比例', 0))
                fw_col = next((c for c in df_h.columns if '飛輪' in c), None)
                flywheel_stage = str(latest.get(fw_col, 'N/A')) if fw_col else 'N/A'
                
                bias_val = "N/A"
                if not df_Market.empty:
                    b_col = next((c for c in df_Market.columns if '乖離' in c), None)
                    if b_col:
                        valid_rows = df_Market[df_Market[b_col].astype(str).str.strip() != '']
                        if not valid_rows.empty: bias_val = valid_rows.iloc[-1][b_col]
                
                vix_val, vix_status = "N/A", ""
                if not df_Global.empty:
                    code_col = next((c for c in df_Global.columns if '代碼' in c), None)
                    if code_col:
                        vix_row = df_Global[df_Global[code_col].astype(str).str.strip().str.upper() == 'VIX']
                        if not vix_row.empty:
                            p_col = next((c for c in df_Global.columns if '價格' in c), None)
                            s_col = next((c for c in df_Global.columns if '狀態' in c), None)
                            if p_col: vix_val = vix_row.iloc[0].get(p_col, 'N/A')
                            if s_col: vix_status = vix_row.iloc[0].get(s_col, '')

                risk_color = "black"
                if "紅" in risk_today: risk_color = "#dc3545"
                elif "橘" in risk_today: risk_color = "#fd7e14"
                elif "黃" in risk_today: risk_color = "#ffc107"
                elif "綠" in risk_today: risk_color = "#28a745"

                m_cols = st.columns(7)
                def make_metric(label, value, color="black"):
                        return f"<div style='margin-bottom:0px;'><div style='font-size:1.1rem; color:gray; margin-bottom:2px; white-space: nowrap;'>{label}</div><div style='font-size:1.8rem; font-weight:bold; color:{color}; line-height:1.2; white-space: normal; word-break: break-word;'>{value}</div></div>"

                with m_cols[0]: st.markdown(make_metric("LDR", ldr_display, ldr_color), unsafe_allow_html=True)
                with m_cols[1]:
                    match = re.search(r"(.+?)\s*([\(（].+?[\)）])", risk_today)
                    if match:
                        r_main = match.group(1).strip()
                        r_sub = match.group(2).strip()
                        r_sub_clean = re.sub(r"[（）\(\)]", "", r_sub)
                        risk_display_html = f"{r_main}<div style='font-size: 1rem; line-height: 1.0; margin-top: 2px; white-space: normal; word-break: break-word;'>{r_sub_clean}</div>"
                    else: risk_display_html = risk_today
                    st.markdown(make_metric("風險等級", risk_display_html, risk_color), unsafe_allow_html=True)
                    
                with m_cols[2]: st.markdown(make_metric("質押率", pledge_display, p_color), unsafe_allow_html=True)
                with m_cols[3]: st.markdown(make_metric("建議拆倉", unwind_rate, "#dc3545" if safe_float(unwind_rate) > 0 else "black"), unsafe_allow_html=True)
                with m_cols[4]:
                    bias_display = "N/A"
                    if bias_val != "N/A":
                            bv = safe_float(bias_val)
                            if abs(bv) >= 1.0: bias_display = f"{bv:.2f}%"
                            else: bias_display = f"{bv*100:.2f}%"
                    val_str = f"{market_pos}<div style='font-size: 1rem; line-height: 1.0; margin-top: 2px;'>{bias_display}</div>"
                    st.markdown(make_metric("盤勢", val_str), unsafe_allow_html=True)
                with m_cols[5]: st.markdown(make_metric("飛輪階段", flywheel_stage), unsafe_allow_html=True)
                with m_cols[6]:
                    v_html = vix_status
                    match = re.search(r"(.+?)\s*([\(（].+?[\)）])", vix_status, re.DOTALL)
                    if match:
                        v_main = match.group(1).strip()
                        v_sub = match.group(2).strip()
                        v_sub_clean = re.sub(r"[（）\(\)]", "", v_sub).replace('\n', ' ')
                        v_html = f"{v_main}<div style='font-size: 1rem; line-height: 1.3; margin-top: 2px; white-space: normal; color: gray;'>{v_sub_clean}</div>"
                    vix_display_html = f"{vix_val}<div style='font-size: 1rem; line-height: 1.2; margin-top: 2px;'>{v_html}</div>"
                    st.markdown(make_metric("VIX", vix_display_html), unsafe_allow_html=True) 
                
                st.markdown(f"<div style='font-size:1.1em;color:gray;margin-top:2px;margin-bottom:2px'>📊 操作指令 (60日乖離: {bias_val})</div>", unsafe_allow_html=True)
                st.info(f"{cmd}")
        except Exception as e: st.error(f"解析判斷數據時發生錯誤: {e}")

else: st.warning('總覽數據載入失敗。請檢查 Secrets 設定或試算表網址。')

# 2. 持股
st.header('2. 持股分析')
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("### 📝 持股明細") 
    if not df_A.empty:
        df_show = df_A.copy()
        if st.session_state['live_prices']:
            df_show['即時價'] = df_show['股票'].map(st.session_state['live_prices']).fillna('')
        
        for c in ['持有數量（股）', '市值（元）', '浮動損益']: 
            if c in df_show.columns: df_show[c] = df_show[c].apply(fmt_int)
        for c in ['平均成本', '收盤價', '即時價']:
            if c in df_show.columns: df_show[c] = df_show[c].apply(fmt_money)
            
        height_val = (len(df_show) + 1) * 35 + 20
        st.dataframe(df_show, use_container_width=True, height=height_val, hide_index=True)

with c2:
    st.markdown("<h3 style='text-align: center;'>🍰 資產配置</h3>", unsafe_allow_html=True) 
    if not df_B.empty and '市值（元）' in df_B.columns:
        df_B['num'] = df_B['市值（元）'].apply(safe_float)
        chart_data = df_B[(df_B['num'] > 0) & (~df_B['股票'].str.contains('總資產|Total', na=False))]
        if not chart_data.empty:
            fig = px.pie(chart_data, values='num', names='股票')
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig, use_container_width=True)

# 3. 交易紀錄
st.header('3. 交易紀錄與淨值')
t1, t2, t3 = st.tabs(['現金流', '已實現損益', '每日淨值'])

with t1:
    if not df_D.empty:
        df_calc = df_D.copy()
        if '日期' in df_calc.columns:
            df_calc['dt'] = pd.to_datetime(df_calc['日期'], errors='coerce')
            df_calc.sort_values('dt', ascending=False, inplace=True)
        cats = df_calc['動作'].unique().tolist()
        sel = st.multiselect('篩選動作', cats, default=cats)
        df_calc = df_calc[df_calc['動作'].isin(sel)]
        total = df_calc['淨收／支出'].apply(safe_float).sum() if '淨收／支出' in df_calc.columns else 0
        c_a, c_b = st.columns(2)
        c_a.metric("篩選淨額", fmt_money(total))
        c_b.markdown(f"**筆數：** {len(df_calc)}")
        df_view = df_calc.drop(columns=['dt'], errors='ignore').copy()
        if '日期' in df_view.columns: df_view['日期'] = df_view['日期'].apply(fmt_date)
        for c in ['淨收／支出', '累積現金', '成交價']:
            if c in df_view.columns: df_view[c] = df_view[c].apply(fmt_money)
        if '數量' in df_view.columns: df_view['數量'] = df_view['數量'].apply(fmt_int)
        st.dataframe(df_view, use_container_width=True, height=400)
        if not df_calc.empty: st.caption(f"📅 {df_calc['dt'].min().date()} ~ {df_calc['dt'].max().date()}")

with t2:
    if not df_E.empty:
        df_calc = df_E.copy()
        d_col = next((c for c in df_calc.columns if '日期' in c), None)
        if d_col:
            df_calc['dt'] = pd.to_datetime(df_calc[d_col], errors='coerce')
            df_calc.sort_values('dt', ascending=False, inplace=True)
        stocks = df_calc['股票'].unique().tolist()
        c_sel, c_all, c_clr = st.columns([4, 1, 1])
        with c_sel: sel_s = st.multiselect('篩選股票', stocks, default=stocks, key='pnl_s', label_visibility="collapsed")
        with c_all:
            st.markdown('<div style="height: 28px"></div>', unsafe_allow_html=True)
            if st.button("全選"): del st.session_state['pnl_s']; st.rerun()
        with c_clr:
            st.markdown('<div style="height: 28px"></div>', unsafe_allow_html=True)
            if st.button("清除"): st.session_state['pnl_s'] = []; st.rerun()
        if sel_s: df_calc = df_calc[df_calc['股票'].isin(sel_s)]
        total = df_calc['已實現損益'].apply(safe_float).sum() if '已實現損益' in df_calc.columns else 0
        st.metric("總實現損益", fmt_money(total))
        df_view = df_calc.drop(columns=['dt'], errors='ignore').copy()
        if d_col: df_view[d_col] = df_view[d_col].apply(fmt_date)
        for c in ['已實現損益', '投資成本', '帳面收入', '成交均價']:
             if c in df_view.columns: df_view[c] = df_view[c].apply(fmt_money)
        st.dataframe(df_view, use_container_width=True, height=400)

with t3:
    if not df_F.empty:
        df_calc = df_F.copy()
        if '實質NAV' in df_calc.columns and '日期' in df_calc.columns:
            df_calc['dt'] = pd.to_datetime(df_calc['日期'], errors='coerce')
            df_calc['nav'] = df_calc['實質NAV'].apply(safe_float)
            df_chart = df_calc.sort_values('dt')
            fig = px.line(df_chart, x='dt', y='nav', title='NAV 趨勢', hover_data={'dt': '|%Y-%m-%d', 'nav': ':,.0f'})
            fig.update_traces(hovertemplate='<b>日期</b>: %{x|%Y-%m-%d}<br><b>淨值</b>: %{y:,.0f}<extra></extra>')
            fig.update_layout(hovermode="x unified", yaxis_tickformat=",.0f")
            st.plotly_chart(fig, use_container_width=True)
            with st.expander("詳細數據"):
                df_disp = df_calc.sort_values('dt', ascending=False).drop(columns=['dt', 'nav']).copy()
                df_disp['日期'] = df_disp['日期'].apply(fmt_date)
                for c in ['實質NAV', '股票市值', '現金']:
                    if c in df_disp.columns: df_disp[c] = df_disp[c].apply(fmt_money)
                st.dataframe(df_disp, use_container_width=True)
                if not df_calc.empty: st.caption(f"📅 紀錄: {df_calc['dt'].min().date()} ~ {df_calc['dt'].max().date()}")

st.markdown('---')
# 4. 財富藍圖
st.header('4. 財富藍圖')
if not df_G.empty:
    try:
        all_rows = [df_G.columns.tolist()] + df_G.values.tolist()
        current_title = None
        current_data = []
        found_sections = False 
        
        for row in all_rows:
            first_cell = str(row[0]).strip()
            if first_cell.startswith(('一、', '二、', '三、', '四、', '五、')):
                found_sections = True
                if current_title:
                    title_match = re.search(r"(.+?)\s*[（\(](.+)[）\)]", current_title)
                    if title_match:
                        main_t = title_match.group(1).strip()
                        sub_t = title_match.group(2).strip()
                        st.markdown(f"### {main_t}")
                        st.markdown(f"<div style='font-size: 0.9em; color: gray; margin-top: -0.5rem; margin-bottom: 0.8rem;'>（{sub_t}）</div>", unsafe_allow_html=True)
                    else:
                        st.subheader(current_title)
                        
                    if len(current_data) > 0:
                        headers = current_data[0]
                        body = current_data[1:] if len(current_data) > 1 else []
                        u_heads = []
                        seen = {}
                        for h in headers:
                            h_str = str(h).strip()
                            if not h_str: h_str = "-" 
                            if h_str in seen: seen[h_str] += 1; u_heads.append(f"{h_str}_{seen[h_str]}")
                            else: seen[h_str] = 0; u_heads.append(h_str)
                        if body:
                            st.dataframe(pd.DataFrame(body, columns=u_heads), use_container_width=True, hide_index=True)
                current_title = first_cell
                current_data = []
            elif any(str(c).strip() for c in row):
                if current_title is not None:
                    current_data.append(row)
        
        # Render last
        if current_title:
            title_match = re.search(r"(.+?)\s*[（\(](.+)[）\)]", current_title)
            if title_match:
                main_t = title_match.group(1).strip()
                sub_t = title_match.group(2).strip()
                st.markdown(f"### {main_t}")
                st.markdown(f"<div style='font-size: 0.9em; color: gray; margin-top: -0.5rem; margin-bottom: 0.8rem;'>（{sub_t}）</div>", unsafe_allow_html=True)
            else:
                st.subheader(current_title)
            
            if len(current_data) > 0:
                headers = current_data[0]
                body = current_data[1:] if len(current_data) > 1 else []
                u_heads = []
                seen = {}
                for h in headers:
                    h_str = str(h).strip()
                    if not h_str: h_str = "-" 
                    if h_str in seen: seen[h_str] += 1; u_heads.append(f"{h_str}_{seen[h_str]}")
                    else: seen[h_str] = 0; u_heads.append(h_str)
                if body:
                    st.dataframe(pd.DataFrame(body, columns=u_heads), use_container_width=True, hide_index=True)
        
        if not found_sections:
            st.dataframe(df_G, use_container_width=True)

    except:
        st.dataframe(df_G, use_container_width=True)
else:
    st.info("無財富藍圖資料")
