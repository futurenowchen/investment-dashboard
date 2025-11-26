import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import yfinance as yf 
import gspread 
import time 
import re 
import numpy as np

# 設置頁面配置
st.set_page_config(layout="wide")

# 注入 CSS (修正按鈕樣式)
st.markdown("""
<style>
/* 字體大小調整 */
html, body, [class*="stApp"] { font-size: 16px; }
h1 { font-size: 2.5em; } 
h2 { font-size: 1.8em; } 
h3 { font-size: 1.5em; } 
.stDataFrame { font-size: 1.0em; } 
.stMetric > div:first-child { font-size: 1.25em !important; }
.stMetric > div:nth-child(2) > div:first-child { font-size: 2.5em !important; }

/* 側邊欄按鈕樣式 */
div[data-testid="stSidebar"] .stButton button {
    width: 100%;
    height: 45px; 
    margin-bottom: 10px;
    border: 1px solid #ccc;
}

/* 隱藏 Multiselect 的標籤 */
div[data-testid="stMultiSelect"] > label { display: none; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 
# ==============================================================================

# 初始化 Session State
if 'live_prices' not in st.session_state:
    st.session_state['live_prices'] = {} 

# --- 核心工具函式：安全數值轉換 (向量化版本) ---
def safe_numeric(series):
    """
    接收一個 pandas Series (整欄資料)，安全的轉換為數字。
    處理千分位、貨幣符號、百分比等。
    """
    # 1. 強制轉為字串
    s = series.astype(str)
    # 2. 移除常見非數字字符 (使用向量化字串操作)
    s = s.str.replace(',', '', regex=False)
    s = s.str.replace('$', '', regex=False)
    s = s.str.replace('¥', '', regex=False)
    s = s.str.replace('%', '', regex=False)
    s = s.str.replace('萬', '0000', regex=False)
    s = s.str.replace('(', '-', regex=False).str.replace(')', '', regex=False)
    # 3. 轉換為數字，無法轉換的變為 NaN
    return pd.to_numeric(s, errors='coerce').fillna(0)

# 連線工具函式
def get_gsheet_connection():
    try:
        if "gsheets" not in st.secrets.get("connections", {}):
            st.error("Secrets 錯誤：找不到 [connections.gsheets] 區塊。")
            return None, None
        if SHEET_URL == "YOUR_SPREADSHEET_URL_HERE":
            st.error("❌ 程式碼錯誤：請先將 SHEET_URL 替換為您的 Google Sheets 完整網址！")
            return None, None
        secrets_config = st.secrets["connections"]["gsheets"]
        credentials_info = dict(secrets_config) 
        credentials_info["private_key"] = credentials_info["private_key"].replace('\\n', '\n')
        gc = gspread.service_account_from_dict(credentials_info)
        spreadsheet = gc.open_by_url(SHEET_URL)
        return gc, spreadsheet
    except Exception as e:
        st.error(f"⚠️ 連線錯誤: {e}")
        return None, None

# 數據載入函式 (只讀取原始字串，不做轉換，保證不崩潰)
@st.cache_data(ttl=None) 
def load_data(sheet_name): 
    with st.spinner(f"正在讀取: '{sheet_name}'..."):
        try:
            _, spreadsheet = get_gsheet_connection()
            if not spreadsheet: return pd.DataFrame()
            
            worksheet = spreadsheet.worksheet(sheet_name) 
            data = worksheet.get_all_values() 
            
            # 建立 DataFrame
            if not data: return pd.DataFrame()
            df = pd.DataFrame(data[1:], columns=data[0])
            
            # 修正重複欄位名稱
            if len(df.columns) != len(set(df.columns)):
                new_cols = []
                seen = {}
                for col in df.columns:
                    clean_col = "Unnamed" if not col else col
                    if clean_col in seen:
                        seen[clean_col] += 1
                        new_cols.append(f"{clean_col}_{seen[clean_col]}")
                    else:
                        seen[clean_col] = 0
                        new_cols.append(clean_col)
                df.columns = new_cols
            
            return df # 返回純字串 DataFrame
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"找不到工作表 '{sheet_name}'")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"讀取 '{sheet_name}' 失敗: {e}")
            return pd.DataFrame() 

# 獲取股價函式
@st.cache_data(ttl="60s") 
def fetch_current_prices(valid_tickers):
    st.info(f"獲取 {len(valid_tickers)} 支股票價格中...")
    price_updates = {}
    time.sleep(1) 
    try:
        data = yf.download(valid_tickers, period='1d', interval='1d', progress=False)
        if data.empty: return {}
        
        if len(valid_tickers) == 1:
            latest_prices = data['Close'].iloc[-1] 
            if not pd.isna(latest_prices):
                price_updates[valid_tickers[0]] = round(latest_prices, 4)
        else:
            latest_prices_df = data['Close'].iloc[-1]
            for ticker in valid_tickers:
                price = latest_prices_df.get(ticker)
                if price is not None and not pd.isna(price):
                    price_updates[ticker] = round(price, 4)
        return price_updates
    except Exception as e:
        st.error(f"股價獲取錯誤: {e}")
        return {}

# 寫入函式
def write_prices_to_sheet(df_A, price_updates):
    _, spreadsheet = get_gsheet_connection()
    if not spreadsheet: return False
    try:
        worksheet = spreadsheet.worksheet('表A_持股總表')
        write_values = []
        for index, row in df_A.iterrows():
            ticker = str(row['股票']).strip()
            price = price_updates.get(ticker) 
            write_values.append([f"{price}"]) if price is not None else write_values.append([''])
        
        start_row = 2 
        end_row = start_row + len(write_values) - 1
        range_to_update = f'E{start_row}:E{end_row}'
        worksheet.update(range_to_update, write_values, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"寫入失敗: {e}")
        return False

# ======================== 應用程式主體 ========================

st.title('💰 投資組合儀表板')

# 載入數據 (這裡只讀取字串，絕對安全)
df_A = load_data('表A_持股總表')
df_B = load_data('表B_持股比例')
df_C = load_data('表C_總覽')
df_D = load_data('表D_現金流')
df_E = load_data('表E_已實現損益')
df_F = load_data('表F_每日淨值')
df_G = load_data('表G_財富藍圖') 

# --- 側邊欄功能 ---
st.sidebar.header("🎯 數據管理")

if st.sidebar.button("🔄 重新載入所有數據"):
    load_data.clear()
    st.rerun()

st.sidebar.markdown("---")

if st.sidebar.button("💾 獲取股價並寫入 Sheets", type="primary"):
    if not df_A.empty and '股票' in df_A.columns:
        tickers = df_A['股票'].astype(str).str.strip().unique()
        valid_tickers = [t for t in tickers if t]
        if valid_tickers:
            updates = fetch_current_prices(valid_tickers)
            st.session_state['live_prices'] = updates
            if updates and write_prices_to_sheet(df_A, updates):
                st.sidebar.success("更新成功！正在重新載入...")
                load_data.clear()
                st.rerun()
        else:
            st.sidebar.warning("未找到股票代碼")
    else:
        st.sidebar.error("表A 缺少 '股票' 欄位")

# --- 1. 投資總覽 ---
st.header('1. 投資總覽') 
if not df_C.empty:
    # 處理總覽數據
    df_C_disp = df_C.copy()
    # 轉置處理：確保項目在索引，數值在第一欄
    df_C_disp.set_index(df_C_disp.columns[0], inplace=True)
    val_col = df_C_disp.columns[0] # 取得數值欄位名稱
    
    # 讀取指標
    risk_raw = str(df_C_disp.loc['β風險燈號', val_col] if 'β風險燈號' in df_C_disp.index else '未知')
    risk_clean = re.sub(r'\s+', '', risk_raw)
    leverage_raw = df_C_disp.loc['槓桿倍數β', val_col] if '槓桿倍數β' in df_C_disp.index else 0
    leverage = safe_numeric(pd.Series([leverage_raw]))[0]

    # 燈號邏輯
    colors = {'安全': ('#28a745', '✅', 'white'), '警戒': ('#ffc107', '⚠️', 'black'), '危險': ('#dc3545', '🚨', 'white')}
    c_code, emoji, txt_col = colors.get('安全') # 預設
    for k, v in colors.items():
        if k in risk_clean:
            c_code, emoji, txt_col = v
            break

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader('核心資產')
        # 排除指標行顯示
        mask = ~df_C_disp.index.isin(['β風險燈號', '槓桿倍數β', '短期財務目標', '短期財務目標差距', '達成進度'])
        st.dataframe(df_C_disp[mask], use_container_width=True)
    
    with c2:
        st.subheader('風險指標')
        st.markdown(f"<div style='background:{c_code};color:{txt_col};padding:15px;border-radius:10px;text-align:center;font-weight:bold;font-size:1.5em'>{emoji} {risk_raw}</div>", unsafe_allow_html=True)
        st.metric("槓桿倍數 β", f"{leverage:.2f}")
        
        st.markdown("---")
        st.write("**財務目標進度**")
        # 目標進度計算
        try:
            t_val = safe_numeric(pd.Series([df_C_disp.loc['短期財務目標', val_col]]))[0]
            gap_val = safe_numeric(pd.Series([df_C_disp.loc['短期財務目標差距', val_col]]))[0]
            
            if t_val > 0:
                curr = t_val - gap_val
                prog = min(1.0, max(0.0, curr / t_val))
                st.progress(prog)
                st.caption(f"{curr:,.0f} / {t_val:,.0f} ({prog*100:.1f}%)")
        except Exception:
            st.caption("無法計算目標進度")

# --- 2. 持股分析 ---
st.header('2. 持股分析')
c1, c2 = st.columns([1, 1])
with c1:
    if not df_A.empty:
        df_A_show = df_A.copy()
        # 安全轉換數值以供顯示
        num_cols = ['持有數量（股）', '平均成本', '收盤價', '市值（元）', '浮動損益']
        for c in num_cols:
            if c in df_A_show.columns:
                # 先轉數字再格式化，避免錯誤
                nums = safe_numeric(df_A_show[c])
                df_A_show[c] = nums.apply(lambda x: f"{x:,.2f}")
        
        # 處理即時股價顯示
        if st.session_state['live_prices']:
            df_A_show['即時價'] = df_A_show['股票'].astype(str).str.strip().map(st.session_state['live_prices'])
        
        with st.expander("持股明細", expanded=True):
            st.dataframe(df_A_show, use_container_width=True)

with c2:
    if not df_B.empty and '市值（元）' in df_B.columns:
        # 轉換數值用於繪圖
        df_B['市值_num'] = safe_numeric(df_B['市值（元）'])
        # 排除總資產
        df_chart = df_B[~df_B['股票'].str.contains('總資產|Total', na=False)]
        df_chart = df_chart[df_chart['市值_num'] > 0]
        
        if not df_chart.empty:
            fig = px.pie(df_chart, values='市值_num', names='股票', title='投資組合比例')
            st.plotly_chart(fig, use_container_width=True)

# --- 3. 交易紀錄 ---
st.header('3. 交易紀錄與淨值')
tab1, tab2, tab3 = st.tabs(['現金流', '已實現損益', '每日淨值'])

# 通用格式化 lambda
fmt_num = lambda x: f"{x:,.2f}"
fmt_int = lambda x: f"{x:,.0f}"

with tab1:
    if not df_D.empty:
        df_D['淨收／支出_num'] = safe_numeric(df_D['淨收／支出'])
        df_D['日期_dt'] = pd.to_datetime(df_D['日期'], errors='coerce')
        df_D = df_D.sort_values('日期_dt', ascending=False)
        
        cats = df_D['動作'].unique().tolist()
        sel_cats = st.multiselect('篩選動作', cats, default=cats)
        df_show = df_D[df_D['動作'].isin(sel_cats)]
        
        st.metric("篩選總額", f"{df_show['淨收／支出_num'].sum():,.0f}")
        
        # 顯示用表格處理
        df_disp = df_show.drop(columns=['淨收／支出_num', '日期_dt']).copy()
        # 格式化
        for c in ['淨收／支出', '累積現金', '成交價']:
             if c in df_disp.columns: df_disp[c] = safe_numeric(df_disp[c]).apply(fmt_num)
        if '數量' in df_disp.columns: df_disp['數量'] = safe_numeric(df_disp['數量']).apply(fmt_int)
            
        st.dataframe(df_disp, use_container_width=True, hide_index=True)

with tab2:
    if not df_E.empty:
        df_E['損益_num'] = safe_numeric(df_E['已實現損益'])
        # 嘗試找日期欄位
        date_col = next((c for c in df_E.columns if '日期' in c), None)
        if date_col:
            df_E[date_col] = pd.to_datetime(df_E[date_col], errors='coerce')
            df_E = df_E.sort_values(date_col, ascending=False)
            # 將日期轉回字串以便顯示
            df_E[date_col] = df_E[date_col].dt.strftime('%Y-%m-%d')

        stocks = df_E['股票'].unique().tolist()
        c1, c2, c3 = st.columns([4, 1, 1])
        with c1: sel = st.multiselect('篩選股票', stocks, default=stocks, key='pnl_sel', label_visibility="collapsed")
        with c2: 
            if st.button('全選'): 
                st.session_state.pop('pnl_sel', None) # 清除 state 讓 default 生效 (需重整)
                st.rerun()
        with c3: 
            if st.button('清除'): 
                # 這裡比較 tricky, multiselect 預設全選很難用 state 清空，建議直接重整
                pass 

        df_show = df_E[df_E['股票'].isin(sel)] if sel else pd.DataFrame(columns=df_E.columns)
        st.metric("總實現損益", f"{df_show['損益_num'].sum():,.0f}")
        
        # 顯示處理
        df_disp = df_show.drop(columns=['損益_num']).copy()
        num_fmt_cols = ['已實現損益', '投資成本', '帳面收入', '成交均價']
        for c in num_fmt_cols:
             if c in df_disp.columns: df_disp[c] = safe_numeric(df_disp[c]).apply(fmt_num)
        
        st.dataframe(df_disp, use_container_width=True, hide_index=True)

with tab3:
    if not df_F.empty:
        df_F['NAV_num'] = safe_numeric(df_F['實質NAV'])
        df_F['日期_dt'] = pd.to_datetime(df_F['日期'], errors='coerce')
        
        # 圖表
        fig = px.line(df_F.sort_values('日期_dt'), x='日期_dt', y='NAV_num', title='NAV 趨勢')
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("詳細數據"):
            df_disp = df_F.sort_values('日期_dt', ascending=False).copy()
            df_disp['日期'] = df_disp['日期_dt'].dt.strftime('%Y-%m-%d')
            cols = ['實質NAV', '股票市值', '現金']
            for c in cols:
                 if c in df_disp.columns: df_disp[c] = safe_numeric(df_disp[c]).apply(fmt_num)
            
            st.dataframe(df_disp.drop(columns=['NAV_num', '日期_dt']), use_container_width=True)

# 4. 財富藍圖
st.markdown('---')
if not df_G.empty:
    with st.expander('4. 財富藍圖 (表G)', expanded=False):
        st.dataframe(df_G, use_container_width=True)
