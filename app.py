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
div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] .stButton button {
    width: 100%; height: 40px; margin-bottom: 5px;
}
div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton > button,
div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] > div:nth-child(3) .stButton > button {
    margin-top: 25px; height: 35px;
}
div[data-testid="stMultiSelect"] > label { display: none; }
</style>
""", unsafe_allow_html=True)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 

if 'live_prices' not in st.session_state:
    st.session_state['live_prices'] = {} 

# --- 輔助格式化函式 ---
def fmt_currency(val):
    """將數值格式化為貨幣字串 (1,234.56)"""
    try:
        num = float(val)
        return f"{num:,.2f}"
    except (ValueError, TypeError):
        return val

def fmt_number(val):
    """將數值格式化為整數字串 (1,234)"""
    try:
        num = float(val)
        return f"{num:,.0f}"
    except (ValueError, TypeError):
        return val

def fmt_date(val):
    """將日期格式化為 YYYY-MM-DD"""
    if isinstance(val, pd.Timestamp):
        return val.strftime('%Y-%m-%d')
    return str(val)

# 數值清潔函式 (僅用於移除 Sheets 格式化符號)
def clean_sheets_value(value):
    if value is None or not isinstance(value, str):
        return value
    s = value.strip()
    s = s.replace(',', '').replace('$', '').replace('¥', '').replace('%', '').replace('萬', '0000')
    s = s.replace('(', '-').replace(')', '') 
    return s if s else np.nan

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
        st.error(f"⚠️ 連線至 Google Sheets 發生錯誤。")
        return None, None

# 數據載入函式
@st.cache_data(ttl=None) 
def load_data(sheet_name): 
    with st.spinner(f"正在載入工作表: '{sheet_name}'..."):
        try:
            _, spreadsheet = get_gsheet_connection()
            if not spreadsheet: return pd.DataFrame()
            
            worksheet = spreadsheet.worksheet(sheet_name) 
            data = worksheet.get_all_values() 
            df = pd.DataFrame(data[1:], columns=data[0])
            
            # 僅對非 '股票' 類的欄位進行字串清理
            for col in df.columns:
                if col not in ['股票', '股票名稱', '用途／股票', '動作', '備註']:
                    df[col] = df[col].astype(str).apply(clean_sheets_value) 

            # 修正重複欄位名稱
            if len(df.columns) != len(set(df.columns)):
                new_cols = []
                seen = {}
                for col in df.columns:
                    clean_col = "Unnamed" if col is None or col == "" else col
                    if clean_col in seen:
                        seen[clean_col] += 1
                        new_cols.append(f"{clean_col}_{seen[clean_col]}")
                    else:
                        seen[clean_col] = 0
                        new_cols.append(clean_col)
                df.columns = new_cols

            df = df.replace('', np.nan) 
            return df
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"GSheets 連線失敗：找不到工作表 '{sheet_name}'。")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"⚠️ 讀取工作表 '{sheet_name}' 發生未知錯誤。")
            return pd.DataFrame() 

# 獲取股價函式
@st.cache_data(ttl="60s") 
def fetch_current_prices(valid_tickers):
    st.info(f"正在從 yfinance 獲取 {len(valid_tickers)} 支股票的最新收盤價...")
    price_updates = {}
    time.sleep(1) 
    try:
        data = yf.download(valid_tickers, period='1d', interval='1d', progress=False)
        if data.empty:
            st.warning("無法從 yfinance 獲取任何數據。")
            return {}
        
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
        st.error(f"❌ 獲取股價時發生錯誤：{e}")
        return {}

# 寫入函式
def write_prices_to_sheet(df_A, price_updates):
    _, spreadsheet = get_gsheet_connection()
    if not spreadsheet: return False
    try:
        worksheet = spreadsheet.worksheet('表A_持股總表')
    except gspread.exceptions.WorksheetNotFound:
        st.error("寫入失敗：找不到工作表 '表A_持股總表'。")
        return False
        
    write_values = []
    for index, row in df_A.iterrows():
        ticker = str(row['股票']).strip()
        price = price_updates.get(ticker) 
        if price is not None:
            write_values.append([f"{price}"]) 
        else:
            write_values.append(['']) 
    
    start_row = 2 
    end_row = start_row + len(write_values) - 1
    range_to_update = f'E{start_row}:E{end_row}'
    worksheet.update(range_to_update, write_values, value_input_option='USER_ENTERED')
    return True

# --- 應用程式主體 ---

st.title('💰 投資組合儀表板')

df_A = load_data('表A_持股總表')
df_B = load_data('表B_持股比例')
df_C = load_data('表C_總覽')
df_D = load_data('表D_現金流')
df_E = load_data('表E_已實現損益')
df_F = load_data('表F_每日淨值')
df_G = load_data('表G_財富藍圖') 

# 側邊欄
st.sidebar.header("🎯 股價數據管理")

if st.sidebar.button("💾 獲取即時價格並寫入 Sheets", type="primary"):
    if df_A.empty or '股票' not in df_A.columns:
        st.sidebar.error("❌ '表A_持股總表' 數據不完整。")
    else:
        tickers = df_A['股票'].astype(str).str.strip().unique()
        valid_tickers = [t for t in tickers if t]
        if not valid_tickers:
            st.sidebar.warning("找不到有效的股票代碼。")
        else:
            price_updates = fetch_current_prices(valid_tickers)
            st.session_state['live_prices'] = price_updates 
            if price_updates:
                if write_prices_to_sheet(df_A, price_updates):
                    st.sidebar.success(f"🎉 成功寫入 {len(price_updates)} 筆價格！")
                    load_data.clear()
                    st.rerun() 
                else:
                    st.sidebar.error("❌ 寫入失敗。")
            else:
                st.sidebar.warning("獲取價格失敗。")
st.sidebar.caption("💡 點擊此按鈕，價格會寫入 Google Sheets 的 E 欄。")

if st.sidebar.button("🔄 立即重新載入 Sheets 數據"):
    load_data.clear() 
    st.session_state['live_prices'] = {} 
    st.sidebar.success("✅ 已清除快取並重新載入。")
    st.rerun() 
st.sidebar.caption("💡 強制從 Google Sheets 獲取最新資料。")
st.sidebar.markdown("---")

# 1. 投資總覽
st.header('1. 投資總覽') 
if not df_C.empty:
    df_C_display = df_C.copy()
    df_C_display.set_index(df_C_display.columns[0], inplace=True)
    if df_C_display.columns.size > 0:
        df_C_display.rename(columns={df_C_display.columns[0]: '數值'}, inplace=True)
        series_C = df_C_display['數值']
    else:
        series_C = df_C_display.iloc[:, 0]

    risk_level_raw = str(series_C.get('β風險燈號', 'N/A'))
    risk_level = risk_level_raw.strip().replace(" ", "") 
    leverage = str(series_C.get('槓桿倍數β', 'N/A'))

    color_mapping = {
        '安全': {'emoji': '✅', 'bg': '#28a745', 'text': 'white'}, 
        '警戒': {'emoji': '⚠️', 'bg': '#ffc107', 'text': 'black'}, 
        '危險': {'emoji': '🚨', 'bg': '#dc3545', 'text': 'white'}, 
    }
    if '安全' in risk_level: style = color_mapping['安全']
    elif '警戒' in risk_level: style = color_mapping['警戒']
    elif '危險' in risk_level: style = color_mapping['危險']
    else: style = {'color': 'gray', 'emoji': '❓', 'bg': '#6c757d', 'text': 'white'}
        
    final_risk_level_text = risk_level_raw if risk_level != 'N/A' else '未知'
    
    col_summary, col_indicators = st.columns([2, 1])
    
    with col_summary:
        st.subheader('核心資產數據')
        exclude_cols = ['β風險燈號', '槓桿倍數β', '短期財務目標', '短期財務目標差距', '達成進度']
        df_display = df_C_display[~df_C_display.index.isin(exclude_cols)].reset_index()
        df_display.columns = ['項目', '數值']
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    with col_indicators:
        st.subheader('風險指標')
        st.markdown(f"<h3 style='text-align: center; color: {style['text']}; background-color: {style['bg']}; border: 2px solid {style['bg']}; padding: 15px; border-radius: 8px; font-weight: bold;'>{style['emoji']} {final_risk_level_text}</h3>", unsafe_allow_html=True)
        try: leverage_value = f"{float(leverage):.4f}"
        except ValueError: leverage_value = str(leverage)
        st.metric(label='槓桿倍數 β', value=leverage_value, delta_color='off')
        
        st.markdown("---")
        st.subheader('🎯 財富目標進度')
        target_name = '短期財務目標'
        gap_name = '短期財務目標差距'
        target_val = pd.to_numeric(clean_sheets_value(series_C.get(target_name)), errors='coerce')
        gap_val = pd.to_numeric(clean_sheets_value(series_C.get(gap_name)), errors='coerce')
        
        if pd.notna(target_val) and pd.notna(gap_val) and target_val > 0:
            current = target_val - gap_val
            pct = (current / target_val)
            st.markdown(f"**{target_name}** ({min(100, pct*100):.2f}%)")
            st.progress(min(1.0, pct))
            st.caption(f"目前: {current:,.0f} / 目標: {target_val:,.0f} (差: {gap_val:,.0f})")
        else:
            st.caption(f"請檢查 '表C_總覽' 中 '{target_name}' 與 '{gap_name}' 的數值。")
else:
    st.warning('總覽數據載入失敗。')

# 2. 持股分析
st.header('2. 持股分析')
col_data, col_chart = st.columns([1, 1])

with col_data:
    if not df_A.empty:
        df_A_disp = df_A.copy()
        if st.session_state['live_prices']:
            df_A_disp['即時收盤價'] = df_A_disp['股票'].astype(str).str.strip().map(st.session_state['live_prices']).fillna('')
            cols = ['即時收盤價'] + [c for c in df_A_disp.columns if c != '即時收盤價']
            df_A_disp = df_A_disp[cols]
            
        # 🎯 修正：先將數值轉為字串格式，再顯示，避開 style.format 崩潰
        for col in ['持有數量（股）', '平均成本', '收盤價', '市值（元）', '浮動損益', '即時收盤價']:
            if col in df_A_disp.columns:
                df_A_disp[col] = pd.to_numeric(df_A_disp[col], errors='coerce').apply(fmt_currency)
        
        with st.expander('持股總表 (表A_持股總表)', expanded=True):
            st.dataframe(df_A_disp, use_container_width=True)

with col_chart:
    if not df_B.empty and '市值（元）' in df_B.columns:
        try:
            df_B['市值（元）'] = pd.to_numeric(df_B['市值（元）'], errors='coerce')
            df_chart = df_B[(df_B['市值（元）'] > 0) & (~df_B['股票'].astype(str).str.contains('總資產', na=False))]
            if not df_chart.empty:
                fig = px.pie(df_chart, values='市值（元）', names='股票', title='📊 投資組合比例')
                st.plotly_chart(fig, use_container_width=True)
        except Exception: pass

# 3. 交易紀錄
st.header('3. 交易紀錄與淨值追蹤')
tab1, tab2, tab3 = st.tabs(['現金流', '已實現損益', '每日淨值'])

with tab1:
    if not df_D.empty and '淨收／支出' in df_D.columns:
        try:
            df_D_clean = df_D.copy()
            df_D_clean['淨收／支出'] = pd.to_numeric(df_D_clean['淨收／支出'], errors='coerce').fillna(0)
            df_D_clean['日期'] = pd.to_datetime(df_D_clean['日期'], errors='coerce')
            df_D_clean.sort_values(by='日期', ascending=False, inplace=True)
            
            cats = df_D_clean['動作'].unique().tolist()
            sel_cats = st.multiselect('篩選動作 (預設全選)', cats, default=cats, key='cf_filter')
            
            df_view = df_D_clean[df_D_clean['動作'].isin(sel_cats)] if sel_cats else pd.DataFrame()
            
            c1, c2 = st.columns(2)
            c1.metric(f"💰 篩選總額", f"{df_view['淨收／支出'].sum():,.2f}")
            c2.markdown(f"**筆數：** {len(df_view)}")
            
            # 🎯 預先格式化為字串
            df_view['日期'] = df_view['日期'].apply(fmt_date)
            for col in ['淨收／支出', '累積現金', '成交價']:
                if col in df_view.columns: df_view[col] = df_view[col].apply(fmt_currency)
            df_view['數量'] = df_view['數量'].apply(fmt_number)
            
            st.dataframe(df_view, use_container_width=True, height=300)
        except Exception as e: st.error(f"現金流錯誤: {e}")
    else: st.warning("無現金流數據")

with tab2:
    if not df_E.empty and '已實現損益' in df_E.columns:
        try:
            df_E_clean = df_E.copy()
            df_E_clean['已實現損益'] = pd.to_numeric(df_E_clean['已實現損益'], errors='coerce').fillna(0)
            
            date_col = next((c for c in df_E_clean.columns if '日期' in c), None)
            if date_col:
                df_E_clean[date_col] = pd.to_datetime(df_E_clean[date_col], errors='coerce')
                df_E_clean.sort_values(by=date_col, ascending=False, inplace=True)
            
            stocks = df_E_clean['股票'].unique().tolist()
            if 'pnl_sel' not in st.session_state: st.session_state['pnl_sel'] = stocks
            
            c_sel, c_btn1, c_btn2 = st.columns([4, 1, 1])
            with c_sel: st.markdown("##### 篩選股票")
            with c_sel: sel_stocks = st.multiselect('', stocks, key='pnl_sel')
            with c_btn1: 
                if st.button("全選"): st.session_state['pnl_sel'] = stocks; st.rerun()
            with c_btn2: 
                if st.button("清除"): st.session_state['pnl_sel'] = []; st.rerun()
            
            df_view = df_E_clean[df_E_clean['股票'].isin(sel_stocks)] if sel_stocks else pd.DataFrame()
            
            c1, c2 = st.columns(2)
            c1.metric("🎯 總實現報酬", f"{df_view['已實現損益'].sum():,.2f}")
            c2.markdown(f"**筆數：** {len(df_view)}")
            
            # 🎯 預先格式化為字串
            if date_col: df_view[date_col] = df_view[date_col].apply(fmt_date)
            for col in ['已實現損益', '投資成本', '帳面收入', '成交均價']:
                if col in df_view.columns: df_view[col] = df_view[col].apply(fmt_currency)
            if '成交股數' in df_view.columns: df_view['成交股數'] = df_view['成交股數'].apply(fmt_number)
            
            st.dataframe(df_view, use_container_width=True, height=300)
        except Exception as e: st.error(f"損益錯誤: {e}")
    else: st.warning("無損益數據")

with tab3:
    if not df_F.empty and '實質NAV' in df_F.columns:
        try:
            df_F_c = df_F.copy()
            df_F_c['日期'] = pd.to_datetime(df_F_c['日期'], errors='coerce')
            df_F_c['實質NAV'] = pd.to_numeric(df_F_c['實質NAV'], errors='coerce')
            df_F_c.sort_values('日期', ascending=False, inplace=True)
            
            fig = px.line(df_F_c.sort_values('日期'), x='日期', y='實質NAV', title='📈 NAV 趨勢')
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander('查看詳細數據', expanded=False):
                cols = ['日期', '實質NAV', '股票市值', '現金', '槓桿倍數β']
                df_sub = df_F_c.loc[:, df_F_c.columns.isin(cols)]
                # 🎯 預先格式化
                df_sub['日期'] = df_sub['日期'].apply(fmt_date)
                for col in ['實質NAV', '股票市值', '現金']:
                     if col in df_sub.columns: df_sub[col] = df_sub[col].apply(fmt_currency)
                st.dataframe(df_sub, use_container_width=True)
        except Exception: st.warning("每日淨值顯示錯誤")
    else: st.warning("無每日淨值數據")

st.markdown('---')
# 4. 財富藍圖
if not df_G.empty:
    with st.expander('4. 財富藍圖 (表G_財富藍圖)', expanded=False):
        st.dataframe(df_G, use_container_width=True)
