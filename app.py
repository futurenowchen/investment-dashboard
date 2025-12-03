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
html, body, [class*="stApp"] { font-size: 16px; }
h1 { font-size: 2.5em; }
h2 { font-size: 1.8em; }
h3 { font-size: 1.5em; }
.stDataFrame { font-size: 1.0em; }
.stMetric > div:first-child { font-size: 1.25em !important; }
.stMetric > div:nth-child(2) > div:first-child { font-size: 2.5em !important; }

/* 側邊欄按鈕樣式 */
div[data-testid="stSidebar"] .stButton button {
    width: 100%; height: 45px; margin-bottom: 10px; border: 1px solid #ccc;
}

/* 進度條顏色 */
.stProgress > div > div > div > div {
    background-color: #007bff;
}
/* 隱藏 Multiselect 的標籤 */
div[data-testid="stMultiSelect"] > label { display: none; }

/* 🎯 風險燈號 CSS */
.risk-indicator {
    padding: 15px;
    border-radius: 8px;
    text-align: center;
    font-size: 1.5em;
    font-weight: bold;
    margin-bottom: 10px;
    border: 2px solid;
}
</style>
""", unsafe_allow_html=True)

if 'live_prices' not in st.session_state:
    st.session_state['live_prices'] = {}

# --- 核心工具函式 ---
def safe_float(value):
    """將各種髒亂的資料轉為浮點數 (計算用)"""
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
            df_c.set_index(df_c.columns[0], inplace=True)
            col = df_c.columns[0]
            
            items = {
                '股票市值': '股票市值', '現金': '現金', '借款餘額': '借款餘額', 
                '總資產市值': '總資產市值', '實質NAV': '實質NAV', '槓桿倍數β': '槓桿倍數β',
                '短期財務目標': '短期財務目標', '達成進度': '達成進度'
            }
            
            for key, label in items.items():
                val = df_c.loc[key, col] if key in df_c.index else "N/A"
                
                if key == '達成進度':
                    v_float = safe_float(val)
                    if isinstance(val, str) and '%' in val:
                         val_str = f"{v_float:.2f}%"
                    elif v_float <= 1.0:
                         val_str = f"{v_float*100:.2f}%"
                    else:
                         val_str = f"{v_float:.2f}%"

                elif key == '槓桿倍數β':
                     if isinstance(val, str) and '%' in val:
                         val_str = val
                     else:
                         val_str = f"{safe_float(val)*100:.2f}%" 
                elif key in ['股票市值', '現金', '借款餘額', '總資產市值', '實質NAV', '短期財務目標']:
                     val_str = fmt_int(val)
                else:
                     val_str = str(val)
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
                cmd = str(latest.get('今日指令', 'N/A'))
                
                lines.append(f"LDR：{ldr}")
                lines.append(f"風險等級：{risk}")
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
            close_val = live_p if live_p else safe_float(row.get('收盤價', 0))
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
                    beta_val = safe_float(row.get('槓桿倍數β', 0))
                    if beta_val <= 5.0: beta = f"β{beta_val*100:.2f}%"
                    else: beta = f"β{beta_val:.2f}%"
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
    """建立 Google Sheets 連線，包含錯誤處理"""
    try:
        # 檢查 Secrets 結構
        if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
            st.error("❌ Secrets 設定錯誤：找不到 [connections.gsheets]。請檢查 .streamlit/secrets.toml")
            return None, None
            
        secrets = dict(st.secrets["connections"]["gsheets"])
        # 處理 Private Key 換行問題
        if "private_key" in secrets:
            secrets["private_key"] = secrets["private_key"].replace('\\n', '\n')
            
        gc = gspread.service_account_from_dict(secrets)
        
        try:
            sh = gc.open_by_url(SHEET_URL)
            return gc, sh
        except gspread.exceptions.APIError as api_err:
            st.error(f"❌ Google API 權限錯誤：{api_err}")
            st.info(f"請確認您已將試算表分享給機器人 Email: {secrets.get('client_email', '未知')}")
            return None, None
            
    except Exception as e:
        st.error(f"❌ 連線發生未預期的錯誤: {e}")
        return None, None

# 數據載入 (純搬運，不做任何轉換)
@st.cache_data(ttl=None) 
def load_data(sheet_name): 
    with st.spinner(f"讀取: {sheet_name}"):
        try:
            _, sh = get_gsheet_connection()
            if not sh: return pd.DataFrame()
            
            try:
                ws = sh.worksheet(sheet_name) 
                data = ws.get_all_values()
            except gspread.exceptions.WorksheetNotFound:
                # 靜默失敗，回傳空表即可
                return pd.DataFrame()
                
            if not data: return pd.DataFrame()
            
            df = pd.DataFrame(data[1:], columns=data[0])
            
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
            st.error(f"讀取 {sheet_name} 失敗: {e}")
            return pd.DataFrame() 

# --- 股價 API (修復版：自動加 .TW) ---
@st.cache_data(ttl="60s") 
def fetch_current_prices(tickers):
    """
    抓取即時股價，針對純數字代碼自動加上 .TW
    """
    if not tickers: return {}
    
    st.toast(f"正在更新 {len(tickers)} 檔股價...", icon="⏳")
    
    # 1. 建立代碼映射表 (原始代碼 -> Yahoo代碼)
    ticker_map = {}
    query_tickers = []
    
    for t in tickers:
        raw_t = str(t).strip()
        if not raw_t: continue
        
        # 簡單判斷：如果是純數字，假設為台股，加上 .TW
        # 如果您有上櫃股票，需自行調整邏輯或在 Sheet 裡直接寫 .TWO
        if raw_t.isdigit():
            y_t = f"{raw_t}.TW"
        else:
            y_t = raw_t
            
        ticker_map[y_t] = raw_t
        query_tickers.append(y_t)
    
    res = {}
    if not query_tickers: return {}

    try:
        # 2. 下載資料
        # progress=False 隱藏進度條
        data = yf.download(query_tickers, period='1d', interval='1d', progress=False)
        
        if data.empty:
            st.warning("Yahoo Finance 未回傳數據")
            return {}

        # 3. 解析資料 (處理單檔與多檔的差異)
        # yfinance 新版多檔時會回傳 MultiIndex Columns
        
        # 取得最後一筆 Close
        try:
            closes = data['Close']
        except KeyError:
            return {}
            
        if closes.empty: return {}
        
        # 取最後一列 (最新的收盤價)
        last_row = closes.iloc[-1]
        
        if len(query_tickers) == 1:
            # 單檔股票，last_row 是一個 float
            val = last_row
            # 有時會是 Series (取決於版本)，轉為 float
            if hasattr(val, 'item'): val = val.item()
            
            original_ticker = ticker_map[query_tickers[0]]
            res[original_ticker] = round(float(val), 2)
        else:
            # 多檔股票，last_row 是一個 Series，index 是 Yahoo 代碼
            for y_t, original_t in ticker_map.items():
                try:
                    val = last_row.get(y_t)
                    if pd.notna(val):
                         if hasattr(val, 'item'): val = val.item()
                         res[original_t] = round(float(val), 2)
                except:
                    pass
        
        return res
    except Exception as e:
        st.error(f"股價更新發生錯誤: {e}")
        return {}

# 寫入 API
def write_prices_to_sheet(df_A, updates):
    _, sh = get_gsheet_connection()
    if not sh: return False
    try:
        ws = sh.worksheet('表A_持股總表')
        # 準備要寫入的資料列表
        vals = []
        for _, row in df_A.iterrows():
            t = str(row.get('股票','')).strip()
            # 從 updates 字典找價格
            p = updates.get(t)
            if p:
                vals.append([p]) 
            else:
                vals.append(['']) # 如果沒抓到價格，填空或保留原值? 這裡先填空
        
        # 批次更新 E 欄 (從 E2 開始)
        if vals:
            ws.update(f'E2:E{2+len(vals)-1}', vals, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"寫入 Google Sheets 失敗: {e}")
        return False

# === 主程式 ===
# ⚠️ 強制更新標題以確認版本
st.title('💰 投資組合儀表板 (v2025-Update)')

# --- 診斷區塊 (除錯用) ---
with st.expander("🛠️ 連線狀態檢查 (若資料跑不出來請點此)", expanded=False):
    st.write(f"目前設定的 Sheet URL: `{SHEET_URL}`")
    if "connections" in st.secrets:
        st.success("✅ Secrets 設定已偵測到")
    else:
        st.error("❌ 找不到 Secrets 設定")

# 載入所有資料
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

# 側邊欄
st.sidebar.header("🎯 數據管理")
if st.sidebar.button("🔄 重新載入資料"):
    load_data.clear()
    st.rerun()

if st.sidebar.button("💾 更新股價至 Google Sheets", type="primary"):
    if not df_A.empty and '股票' in df_A.columns:
        # 取得不重複的股票代碼列表
        tickers = [t for t in df_A['股票'].unique() if str(t).strip()]
        
        # 呼叫修復後的函式
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

# 1. 總覽
st.header('1. 投資總覽')
if not df_C.empty:
    df_c = df_C.copy()
    df_c.set_index(df_c.columns[0], inplace=True)
    col_val = df_c.columns[0]
    
    risk = str(df_c.loc['β風險燈號', col_val]) if 'β風險燈號' in df_c.index else '未知'
    risk_txt = re.sub(r'\s+', '', risk)
    lev = safe_float(df_c.loc['槓桿倍數β', col_val]) if '槓桿倍數β' in df_c.index else 0

    style = {'e':'❓', 'bg':'#6c757d', 't':'white'}
    if '安全' in risk_txt: 
        style = {'e':'✅', 'bg':'#28a745', 't':'white'} # 綠
    elif '警戒' in risk_txt or '警示' in risk_txt: 
        style = {'e':'⚠️', 'bg':'#ffc107', 't':'black'} # 黃 (文字黑)
    elif '危險' in risk_txt: 
        style = {'e':'🚨', 'bg':'#dc3545', 't':'white'} # 紅

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader('核心資產')
        mask = ~df_c.index.isin(['β風險燈號', '槓桿倍數β', '短期財務目標', '短期財務目標差距', '達成進度', 'LDR', 'LDR燈號'])
        st.dataframe(df_c[mask], use_container_width=True)

        # 🎯 今日判斷與市場資訊整合
        if not df_H.empty:
            try:
                df_h = df_H.copy()
                date_col = next((c for c in df_h.columns if '日期' in c), None)
                if date_col:
                    df_h['dt'] = pd.to_datetime(df_h[date_col], errors='coerce')
                    latest = df_h.sort_values('dt', ascending=False).iloc[0]
                    
                    # 取出各項數值
                    ldr_val = str(latest.get('LDR', 'N/A'))
                    risk_today = str(latest.get('今日風險等級', 'N/A'))
                    cmd = str(latest.get('今日指令', 'N/A'))
                    market_pos = str(latest.get('盤勢位置', 'N/A'))
                    
                    # 取得台股60日季線乖離
                    bias_val = "N/A"
                    if not df_Market.empty and '台股60日季線乖離' in df_Market.columns:
                        valid_rows = df_Market[df_Market['台股60日季線乖離'].astype(str).str.strip() != '']
                        if not valid_rows.empty:
                            bias_val = valid_rows.iloc[-1]['台股60日季線乖離']
                    
                    # 取得 VIX 資訊
                    vix_display = "N/A"
                    if not df_Global.empty and '代碼' in df_Global.columns:
                        vix_row = df_Global[df_Global['代碼'] == 'VIX']
                        if not vix_row.empty:
                            v_price = vix_row.iloc[0].get('價格', 'N/A')
                            v_status = vix_row.iloc[0].get('狀態', '')
                            vix_display = f"{v_price} ({v_status})"

                    # 顏色邏輯
                    risk_color = "black"
                    if "紅" in risk_today: risk_color = "#dc3545"
                    elif "黃" in risk_today: risk_color = "#ffc107"
                    elif "綠" in risk_today: risk_color = "#28a745"

                    # 標題
                    st.subheader('📅 今日判斷 & 市場狀態')
                    
                    # 建立四欄顯示 (移除外部灰底 box)
                    m1, m2, m3, m4 = st.columns(4)
                    
                    # 統一的樣式輔助函式 (確保字體大小一致)
                    def make_metric(label, value, color="black"):
                         return f"""
                         <div style='margin-bottom:5px;'>
                            <div style='font-size:0.9rem; color:gray; margin-bottom:0px;'>{label}</div>
                            <div style='font-size:1.6rem; font-weight:bold; color:{color}; line-height:1.2;'>{value}</div>
                         </div>
                         """

                    with m1:
                        st.markdown(make_metric("LDR (槓桿密度)", ldr_val), unsafe_allow_html=True)
                    with m2:
                        st.markdown(make_metric("風險等級", risk_today, risk_color), unsafe_allow_html=True)
                    with m3:
                        val_str = f"{market_pos} ({bias_val})"
                        st.markdown(make_metric("盤勢 / 60日乖離", val_str), unsafe_allow_html=True)
                    with m4:
                        st.markdown(make_metric("VIX 恐慌指數", vix_display), unsafe_allow_html=True)
                    
                    st.markdown("---")
                    
                    # 第二列：指令
                    st.markdown(f"<div style='font-size:0.9em;color:gray;margin-bottom:5px'>📊 操作指令</div>", unsafe_allow_html=True)
                    st.info(f"{cmd}")
                    
            except Exception as e:
                st.error(f"解析判斷數據時發生錯誤: {e}")
    
    with c2:
        st.subheader('風險指標')
        st.markdown(f"<div class='risk-indicator' style='background:{style['bg']};color:{style['t']};border-color:{style['bg']}'>{style['e']} {risk}</div>", unsafe_allow_html=True)
        st.metric("槓桿倍數", f"{lev:.2f}")
        
        st.markdown("---")
        # 財務目標
        try:
            target = safe_float(df_c.loc['短期財務目標', col_val]) if '短期財務目標' in df_c.index else 0
            gap = safe_float(df_c.loc['短期財務目標差距', col_val]) if '短期財務目標差距' in df_c.index else 0
            
            if target > 0:
                curr = target - gap
                pct = max(0.0, min(1.0, curr/target))
                
                st.markdown(f"""
                <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:10px; border:1px solid #e9ecef;">
                    <div style="font-size:1.1em; color:#6c757d; margin-bottom:5px;">短期財務目標達成率</div>
                    <div style="font-size:2.8em; font-weight:bold; color:#007bff; line-height:1.1;">
                        {pct*100:.1f}%
                    </div>
                    <div style="margin-top:8px; font-size:0.95em; display:flex; justify-content:space-between; color:#495057;">
                        <span>目前: <b>{fmt_int(curr)}</b></span>
                        <span>目標: <b>{fmt_int(target)}</b></span>
                    </div>
                     <div style="text-align:right; font-size:0.85em; color:#dc3545; margin-top:2px;">
                        (差 {fmt_int(gap)})
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(pct)
            else:
                st.caption("無法計算進度")
        except: pass

else:
    st.warning('總覽數據載入失敗。請檢查 Secrets 設定或試算表網址。')

# 2. 持股
st.header('2. 持股分析')
c1, c2 = st.columns([1, 1])
with c1:
    # 改用 markdown 確保字體大小控制權
    st.markdown("### 📝 持股明細") 
    if not df_A.empty:
        df_show = df_A.copy()
        if st.session_state['live_prices']:
            df_show['即時價'] = df_show['股票'].map(st.session_state['live_prices']).fillna('')
        
        for c in ['持有數量（股）', '市值（元）', '浮動損益']: 
            if c in df_show.columns: df_show[c] = df_show[c].apply(fmt_int)
        for c in ['平均成本', '收盤價', '即時價']:
            if c in df_show.columns: df_show[c] = df_show[c].apply(fmt_money)
            
        # ⚠️ 強制隱藏 Index 並增加高度
        # 公式調整：每一列約 35px，Header 35px，加上 20px 緩衝
        height_val = (len(df_show) + 1) * 35 + 20
        st.dataframe(df_show, use_container_width=True, height=height_val, hide_index=True)

with c2:
    # 改用 markdown
    st.markdown("### 🍰 資產配置") 
    if not df_B.empty and '市值（元）' in df_B.columns:
        df_B['num'] = df_B['市值（元）'].apply(safe_float)
        chart_data = df_B[(df_B['num'] > 0) & (~df_B['股票'].str.contains('總資產|Total', na=False))]
        if not chart_data.empty:
            fig = px.pie(chart_data, values='num', names='股票')
            # 移除所有邊距
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
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
        if not df_calc.empty:
            st.caption(f"📅 {df_calc['dt'].min().date()} ~ {df_calc['dt'].max().date()}")

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
            
            # 確保日期排序正確 (舊->新)
            df_chart = df_calc.sort_values('dt')
            fig = px.line(df_chart, x='dt', y='nav', title='NAV 趨勢',
                          hover_data={'dt': '|%Y-%m-%d', 'nav': ':,.0f'})
            
            # 懸停優化
            fig.update_traces(hovertemplate='<b>日期</b>: %{x|%Y-%m-%d}<br><b>淨值</b>: %{y:,.0f}<extra></extra>')
            fig.update_layout(hovermode="x unified", yaxis_tickformat=",.0f")
            
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("詳細數據"):
                df_disp = df_calc.sort_values('dt', ascending=False).drop(columns=['dt', 'nav']).copy()
                df_disp['日期'] = df_disp['日期'].apply(fmt_date)
                for c in ['實質NAV', '股票市值', '現金']:
                    if c in df_disp.columns: df_disp[c] = df_disp[c].apply(fmt_money)
                st.dataframe(df_disp, use_container_width=True)
                if not df_calc.empty:
                    st.caption(f"📅 紀錄: {df_calc['dt'].min().date()} ~ {df_calc['dt'].max().date()}")

st.markdown('---')
# 4. 財富藍圖
st.header('4. 財富藍圖')
if not df_G.empty:
    try:
        # 將 DataFrame 還原為列表，以便重新解析結構 (解決標題混在內文的問題)
        all_rows = [df_G.columns.tolist()] + df_G.values.tolist()
        current_title = None
        current_data = []
        
        for row in all_rows:
            first_cell = str(row[0]).strip()
            if first_cell.startswith(('一、', '二、', '三、', '四、', '五、')):
                if current_title:
                    st.subheader(current_title)
                    if len(current_data) > 0:
                        headers = current_data[0]
                        body = current_data[1:] if len(current_data) > 1 else []
                        # 重複欄位處理
                        u_heads = []
                        seen = {}
                        for h in headers:
                            h_str = str(h).strip()
                            if not h_str: h_str = "-" 
                            if h_str in seen: seen[h_str] += 1; u_heads.append(f"{h_str}_{seen[h_str]}")
                            else: seen[h_str] = 0; u_heads.append(h_str)
                        
                        if body:
                            st.dataframe(pd.DataFrame(body, columns=u_heads), use_container_width=True, hide_index=True)
                        else:
                            st.info("無詳細數據")
                current_title = first_cell
                current_data = []
            elif any(str(c).strip() for c in row):
                if current_title is not None:
                    current_data.append(row)
        
        # Render last
        if current_title:
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
    except:
        st.dataframe(df_G, use_container_width=True)
else:
    st.info("無財富藍圖資料")
