import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import yfinance as yf 
import gspread 
import time 
import re 
import numpy as np # 用於處理 NaN

# 設置頁面配置，使用寬佈局以容納更多數據
st.set_page_config(layout="wide")

# 🎯 注入自訂 CSS 來增大整體文字和標題大小
st.markdown("""
<style>
/* 增加應用程式的基礎字體大小 */
html, body, [class*="stApp"] { font-size: 16px; }
/* 增加標題 (Header) 的字體大小 */
h1 { font-size: 2.5em; } 
h2 { font-size: 1.8em; } 
h3 { font-size: 1.5em; } 

/* 增加 Streamlit 內建數據表格的文字大小 */
.stDataFrame { font-size: 1.0em; } 

/* 針對 st.metric 的標籤和數值進行放大 */
.stMetric > div:first-child { font-size: 1.25em !important; }
.stMetric > div:nth-child(2) > div:first-child { font-size: 2.5em !important; }

/* 🎯 按鈕對齊修正 */
/* 修正側邊欄按鈕，讓兩個按鈕上下緊密排列 (Vertical alignment) */
div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] .stButton button {
    width: 100%;
    height: 40px; 
    margin-bottom: 5px; /* 增加按鈕間距 */
}

/* 調整 Tabs 內按鈕的垂直對齊 */
div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton > button,
div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] > div:nth-child(3) .stButton > button {
    margin-top: 25px; 
    height: 35px;
}

/* 隱藏 Multiselect 的標籤 */
div[data-testid="stMultiSelect"] > label { display: none; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🎯 步驟 1：請務必替換成您 Google Sheets 的【完整網址】
# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 
# ==============================================================================


# 初始化 Session State 來儲存即時價格
if 'live_prices' not in st.session_state:
    st.session_state['live_prices'] = {} 


# 🎯 數值清潔函式 (修正：改為處理單一字串，避免 Series 錯誤)
def clean_sheets_value(value):
    """清理單一字串中的格式化符號 (逗號, 萬, % 等)"""
    if value is None or not isinstance(value, str):
        return value
        
    s = value.strip()
    
    # 移除千分位逗號, 貨幣符號, 百分號, 中文計量單位
    s = s.replace(',', '').replace('$', '').replace('¥', '').replace('%', '').replace('萬', '0000')
    s = s.replace('(', '-').replace(')', '') # 處理負數格式 (括號)
    
    return s if s else np.nan

# 🎯 向量化清理函式 (使用 numpy.vectorize 實現對整個 DataFrame 的安全操作)
vectorized_cleaner = np.vectorize(clean_sheets_value)

# 🎯 新增連線工具函式
def get_gsheet_connection():
    """建立並返回 gspread 客戶端和試算表物件。"""
    try:
        if "gsheets" not in st.secrets.get("connections", {}):
            st.error("Secrets 錯誤：找不到 [connections.gsheets] 區塊。請檢查您的 Streamlit Cloud Secrets 配置。")
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
        st.exception(e)
        return None, None


# 數據載入函式 (已修正全域清理衝突)
@st.cache_data(ttl=None) 
def load_data(sheet_name): 
    with st.spinner(f"正在載入工作表: '{sheet_name}'..."):
        try:
            _, spreadsheet = get_gsheet_connection()
            if not spreadsheet:
                return pd.DataFrame()
            
            # --- 獲取數據 ---
            worksheet = spreadsheet.worksheet(sheet_name) 
            data = worksheet.get_all_values() 
            df = pd.DataFrame(data[1:], columns=data[0])
            
            # 🎯 關鍵修正：只對特定的數值相關欄位進行清理 (繞過表G的錯誤)
            
            # 確定需要清理的數值相關欄位 (排除明顯的非數值欄位)
            # 這比之前安全得多，不會嘗試清理像 '一、財富階層對照表...' 這種文字
            numeric_cols = [
                '持有數量（股）', '平均成本', '收盤價', '市值（元）', '浮動損益', '淨收／支出', 
                '累積現金', '實質NAV', '股票市值', '現金', '借款餘額', '總資產市值', 
                '達成進度', '短期財務目標', '短期財務目標差距', '已實現損益', '投資成本', 
                '帳面收入', '成交均價', '成交股數', '槓桿倍數β'
            ]
            
            for col in df.columns:
                if col in numeric_cols:
                    # 應用向量化清理器到字串格式的欄位
                    df[col] = df[col].astype(str).apply(vectorized_cleaner)
                
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

            df = df.replace('', np.nan) # 將空字串替換為 NaN
            return df
        
        # --- 錯誤處理 ---
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"GSheets 連線失敗：找不到工作表 '{sheet_name}'。請檢查名稱是否完全正確。")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"⚠️ 讀取工作表 '{sheet_name}' 發生未知錯誤。")
            st.exception(e) 
            return pd.DataFrame() 

# 🎯 獲取股價函式 (保留快取 60 秒)
@st.cache_data(ttl="60s") 
def fetch_current_prices(valid_tickers):
    """從 yfinance 獲取最新收盤價，並返回價格字典。"""
    
    st.info(f"正在從 yfinance 獲取 {len(valid_tickers)} 支股票的最新收盤價...")
    price_updates = {}
    time.sleep(1) # 增加延遲，避免 yfinance 拒絕請求

    try:
        data = yf.download(valid_tickers, period='1d', interval='1d', progress=False)

        if data.empty:
            st.warning("無法從 yfinance 獲取任何數據，請檢查股票代碼格式 (e.g., 2330.TW)。")
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


# 🎯 新增寫入函式 (用於將股價寫回 Google Sheets)
def write_prices_to_sheet(df_A, price_updates):
    """將最新的價格寫入到 Google Sheets 的 '表A_持股總表' E 欄。"""
    
    # 檢查連線
    _, spreadsheet = get_gsheet_connection()
    if not spreadsheet:
        return False

    try:
        worksheet = spreadsheet.worksheet('表A_持股總表')
    except gspread.exceptions.WorksheetNotFound:
        st.error("寫入失敗：找不到工作表 '表A_持股總表'。")
        return False
        
    # --- 步驟 1: 準備要寫入的數據 ---
    write_values = []
    
    # 遍歷持股總表中的每一行
    for index, row in df_A.iterrows():
        ticker = str(row['股票']).strip()
        price = price_updates.get(ticker) # 從獲取的價格字典中查找價格

        # 🎯 寫入邏輯：如果找到價格，則使用價格，否則寫入空字串或 0
        if price is not None:
            # 寫入 Sheet 時，使用字串，讓 Sheet 執行自己的格式化
            write_values.append([f"{price}"]) 
        else:
            write_values.append(['']) 

    # --- 步驟 2: 執行寫入 ---
    
    # E 欄是第 5 欄 (A=1, B=2, C=3, D=4, E=5)
    # 我們從數據的第 2 行 (A2) 開始寫入，因為第 1 行是標題
    start_row = 2 
    end_row = start_row + len(write_values) - 1
    
    # 寫入範圍: 'E2:E(end_row)'
    range_to_update = f'E{start_row}:E{end_row}'
    
    # 執行批次更新
    worksheet.update(range_to_update, write_values, value_input_option='USER_ENTERED')
    
    return True

# --- 應用程式主體開始 ---

st.title('💰 投資組合儀表板')

# 載入所有需要的數據
df_A = load_data('表A_持股總表')
df_B = load_data('表B_持股比例')
df_C = load_data('表C_總覽')
df_D = load_data('表D_現金流')
df_E = load_data('表E_已實現損益')
df_F = load_data('表F_每日淨值')
df_G = load_data('表G_財富藍圖') 

# 🎯 金額和日期格式化樣式 (確保在全域或主體開始前被定義)
DATE_FORMAT = lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) and isinstance(x, datetime) else str(x)
# CURRENCY_FORMAT 處理 NaN (np.nan) 時是安全的
CURRENCY_FORMAT = lambda x: f"{pd.to_numeric(x, errors='coerce'):,.2f}" if pd.notnull(x) and pd.to_numeric(x, errors='coerce') is not None else ''


# ---------------------------------------------------
# 0. 股價即時更新區塊 (位於側邊欄)
# ---------------------------------------------------
st.sidebar.header("🎯 股價數據管理")

# 🎯 修正：將「獲取即時價格」按鈕和「重新載入」按鈕並列顯示
if st.sidebar.button("💾 獲取即時價格並寫入 Sheets", type="primary"):
    if df_A.empty or '股票' not in df_A.columns:
        st.sidebar.error("❌ '表A_持股總表' 數據不完整或沒有 '股票' 欄位。")
    else:
        tickers = df_A['股票'].astype(str).str.strip().unique()
        valid_tickers = [t for t in tickers if t]
        
        if not valid_tickers:
            st.sidebar.warning("工作表中沒有找到有效的股票代碼。")
        else:
            price_updates = fetch_current_prices(valid_tickers)
            st.session_state['live_prices'] = price_updates 
            
            if price_updates:
                if write_prices_to_sheet(df_A, price_updates):
                    st.sidebar.success(f"🎉 成功寫入 {len(price_updates)} 筆最新價格到 Sheets！")
                    load_data.clear()
                    st.rerun() 
                else:
                    st.sidebar.error("❌ 寫入 Google Sheets 失敗，請檢查連線配置。")

            else:
                st.sidebar.warning("獲取價格失敗，未進行寫入。請檢查股票代碼。")
            
st.sidebar.caption("💡 點擊此按鈕，價格會寫入 Google Sheets 的 E 欄。")

# 🎯 恢復「立即重新載入」按鈕
if st.sidebar.button("🔄 立即重新載入 Sheets 數據"):
    load_data.clear() 
    st.session_state['live_prices'] = {} 
    st.sidebar.success("✅ 所有 Sheets 快取已清除，正在重新載入數據...")
    st.rerun() 
st.sidebar.caption("💡 點擊此按鈕可強制從 Google Sheets 獲取最新資料。")

st.sidebar.markdown("---")


# ---------------------------------------------------
# 1. 投資總覽 (核心總覽表格 + 風險指標燈號 + 目標進度)
# ---------------------------------------------------
st.header('1. 投資總覽') 

if not df_C.empty:
    
    df_C_display = df_C.copy()
    
    # 欄位處理：確保索引設置和欄位名稱唯一性
    df_C_display.set_index(df_C_display.columns[0], inplace=True)
    
    # 將剩下的唯一一欄（數值）重新命名為 '數值'
    if df_C_display.columns.size > 0:
        df_C_display.rename(columns={df_C_display.columns[0]: '數值'}, inplace=True)
        series_C = df_C_display['數值']
    else:
        series_C = df_C_display.iloc[:, 0]

    # 提取關鍵值
    risk_level_raw = str(series_C.get('β風險燈號', 'N/A'))
    risk_level = risk_level_raw.strip().replace(" ", "") 
    leverage = str(series_C.get('槓桿倍數β', 'N/A'))

    # 風險等級顏色判斷邏輯
    color_mapping = {
        '安全': {'emoji': '✅', 'bg': '#28a745', 'text': 'white'}, 
        '警戒': {'emoji': '⚠️', 'bg': '#ffc107', 'text': 'black'}, 
        '危險': {'emoji': '🚨', 'bg': '#dc3545', 'text': 'white'}, 
    }
    
    if '安全' in risk_level:
        style = color_mapping['安全']
    elif '警戒' in risk_level:
        style = color_mapping['警戒']
    elif '危險' in risk_level:
        style = color_mapping['危險']
    else:
        style = {'color': 'gray', 'emoji': '❓', 'bg': '#6c757d', 'text': 'white'}
        
    final_risk_level_text = risk_level_raw if risk_level != 'N/A' else '未知'
    
    col_summary, col_indicators = st.columns([2, 1])
    
    # 左側：顯示總覽數據 
    with col_summary:
        st.subheader('核心資產數據')
        
        # 排除掉單獨作為指標顯示的行，以及用於目標追蹤的行
        exclude_cols = ['β風險燈號', '槓桿倍數β', '短期財務目標', '短期財務目標差距', '達成進度']
        df_display = df_C_display[~df_C_display.index.isin(exclude_cols)].reset_index()
        
        df_display.columns = ['項目', '數值']

        st.dataframe(
            df_display, 
            use_container_width=True, 
            hide_index=True
        )

    # 右側：風險燈號和槓桿倍數 (保持視覺強化)
    with col_indicators:
        st.subheader('風險指標')
        
        # 風險燈號 (使用 HTML 嵌入方式放大字體和顏色)
        html_content = (
            f"<h3 style='text-align: center; color: {style['text']}; background-color: {style['bg']}; border: 2px solid {style['bg']}; padding: 15px; border-radius: 8px; font-weight: bold;'>"
            f"{style['emoji']} {final_risk_level_text}"
            "</h3>"
        )
        st.markdown(html_content, unsafe_allow_html=True)

        # 槓桿倍數 (使用 st.metric 並搭配放大數值)
        try:
            leverage_value = f"{float(leverage):.4f}"
        except ValueError:
            leverage_value = str(leverage)
            
        st.metric(
            label='槓桿倍數 β', 
            value=leverage_value, 
            delta_color='off'
        )
        
        st.markdown("---")
        
        # 🎯 目標進度表 (表C_總覽) 
        st.subheader('🎯 財富目標進度')
        
        target_name_key = '短期財務目標'
        gap_name_key = '短期財務目標差距'

        # 🎯 步驟 1: 提取原始值
        target_value_raw = series_C.get(target_name_key)
        gap_value_raw = series_C.get(gap_name_key)
        
        # 🎯 步驟 2: 轉換為數字 (已在 load_data 中清理字串)
        target = pd.to_numeric(target_value_raw, errors='coerce')
        gap = pd.to_numeric(gap_value_raw, errors='coerce')
        
        # 僅在兩個值都是有效數字且目標大於0時顯示進度條
        if not pd.isna(target) and not pd.isna(gap) and target > 0:
            current = target - gap
            percent_achieved = (current / target)
            display_percent = min(100, round(percent_achieved * 100, 2)) # 進度顯示保留兩位小數
            
            st.markdown(f"**{target_name_key}** ({display_percent:.2f}%)")
            st.progress(min(1.0, percent_achieved)) # st.progress 接受 0.0 到 1.0
            st.caption(f"目前累積: {current:,.0f} / 目標: {target:,.0f} (差距: {gap:,.0f})")
            
            progress_val = series_C.get('達成進度')
            if progress_val:
                st.caption(f"Sheets 中計算的達成進度: {progress_val}")
                
        else:
            missing_info = []
            if pd.isna(target) or target <= 0:
                missing_info.append(f"'{target_name_key}'")
            if pd.isna(gap):
                missing_info.append(f"'{gap_name_key}'")
                
            if missing_info:
                st.caption(f"⚠️ **無法計算進度：** 請檢查 '表C_總覽' 中以下項目的原始數值是否正確。")
            else:
                 st.caption(f"請在 '表C_總覽' 中定義 '{target_name_key}' 和 '{gap_name_key}' 欄位及其數值。")
        

else:
    st.warning('總覽數據載入失敗，請檢查 "表C_總覽"。')

# ---------------------------------------------------
# 2. 持股分析與比例圖 (新增即時股價顯示)
# ---------------------------------------------------
st.header('2. 持股分析')
col_data, col_chart = st.columns([1, 1])

with col_data:
    if not df_A.empty:
        df_display = df_A.copy()
        
        if st.session_state['live_prices']:
            df_display['即時收盤價'] = df_display['股票'].astype(str).str.strip().map(st.session_state['live_prices']).fillna(np.nan)
            
            cols = ['即時收盤價'] + [col for col in df_display.columns if col != '即時收盤價']
            df_display = df_display[cols]
            
        with st.expander('持股總表 (表A_持股總表)', expanded=True):
            # 🎯 格式化持股總表
            st.dataframe(
                df_display.style.format({
                    '持有數量（股）': '{:,.0f}',
                    '平均成本': '{:,.2f}',
                    '收盤價': '{:,.2f}',
                    '市值（元）': '{:,.0f}',
                    '浮動損益': '{:,.0f}',
                    '預估獲利率': '{:.2%}',
                    # 關鍵修正: 處理 NaN 和即時收盤價
                    '即時收盤價': lambda x: f"{pd.to_numeric(x, errors='coerce'):,.2f}" if pd.notna(x) else '',
                }),
                use_container_width=True, 
                hide_index=True
            )

with col_chart:
    if not df_B.empty and '市值（元）' in df_B.columns and '股票' in df_B.columns:
        try:
            # 必須先清理和轉換為數字才能計算
            df_B['市值（元）'] = pd.to_numeric(df_B['市值（元）'], errors='coerce')
            
            # 排除 '總資產' 或類似的總結行
            df_chart = df_B[
                (df_B['市值（元）'] > 0) & 
                (~df_B['股票'].astype(str).str.contains('總資產|Total Asset|總結', na=False))
            ].copy()
            
            if not df_chart.empty:
                fig = px.pie(
                    df_chart, 
                    values='市值（元）', 
                    names='股票', 
                    title='📊 投資組合比例 (排除總資產)'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning('無有效數據可繪製比例圖。')
        except Exception as e:
            st.warning(f'無法產生持股比例圖，請檢查 "表B_持股比例" 數據格式。錯誤: {e}')
    else:
        st.warning('持股比例數據載入失敗，無法繪圖。')


# ---------------------------------------------------
# 3. 交易紀錄與淨值追蹤 (新增篩選功能)
# ---------------------------------------------------
st.header('3. 交易紀錄與淨值追蹤')

# 步驟：定義分頁 Tab
tab1, tab2, tab3 = st.tabs(['現金流', '已實現損益', '每日淨值'])

with tab1:
    # 🎯 現金流表格篩選與統計 - 預設為全選
    if not df_D.empty:
        st.subheader('現金流紀錄 (表D_現金流)')
        
        df_D_clean = df_D.copy()
        
        if '淨收／支出' in df_D_clean.columns and '動作' in df_D_clean.columns and '日期' in df_D_clean.columns:
            try:
                # 數據轉換
                df_D_clean['淨收／支出'] = pd.to_numeric(df_D_clean['淨收／支出'], errors='coerce').fillna(0)
                df_D_clean['累積現金'] = pd.to_numeric(df_D_clean['累積現金'], errors='coerce').fillna(0)
                df_D_clean['數量'] = pd.to_numeric(df_D_clean['數量'], errors='coerce').fillna(0)
                df_D_clean['成交價'] = pd.to_numeric(df_D_clean['成交價'], errors='coerce').fillna(0)
                
                # 處理日期欄位並排序
                df_D_clean['日期'] = pd.to_datetime(df_D_clean['日期'], errors='coerce')
                df_D_clean = df_D_clean.sort_values(by='日期', ascending=False)
                
                available_categories = df_D_clean['動作'].astype(str).unique().tolist()
                selected_categories = st.multiselect(
                    '篩選動作 (預設全選)', 
                    options=available_categories, 
                    default=available_categories, 
                    key='cashflow_filter'
                )
                
                df_D_filtered = df_D_clean[df_D_clean['動作'].isin(selected_categories)] if selected_categories else pd.DataFrame()
                    
                total_cash_flow = df_D_filtered['淨收／支出'].sum()
                
                # 顯示統計數據
                cash_col1, cash_col2 = st.columns(2)
                with cash_col1:
                    st.metric(
                        label=f"💰 篩選淨收／支出總額 ({len(selected_categories)} 個動作)", 
                        value=f"{total_cash_flow:,.2f}",
                        delta=f"{(total_cash_flow / 10000):,.2f} 萬",
                        delta_color="off"
                    )

                with cash_col2:
                    st.markdown(f"**總交易筆數：** {len(df_D_filtered)}")
                
                # 🎯 表格顯示與格式化
                st.dataframe(
                    df_D_filtered.style.format({
                        '日期': DATE_FORMAT,
                        '淨收／支出': CURRENCY_FORMAT,
                        '累積現金': CURRENCY_FORMAT,
                        '數量': '{:,.0f}',
                        '成交價': '{:,.2f}',
                    }), 
                    use_container_width=True, 
                    hide_index=True,
                    height=300 
                )
                
                # 🎯 底部標註
                if not df_D_filtered.empty:
                    valid_dates = df_D_filtered['日期'].dropna()
                    date_min = valid_dates.min() if not valid_dates.empty else 'N/A'
                    date_max = valid_dates.max() if not valid_dates.empty else 'N/A'
                    
                    date_min_str = date_min.strftime('%Y-%m-%d') if isinstance(date_min, datetime) else date_min
                    date_max_str = date_max.strftime('%Y-%m-%d') if isinstance(date_max, datetime) else date_max
                    
                    st.caption(f"📝 數據範圍：**{date_min_str}** ~ **{date_max_str}**，總筆數 **{len(df_D_filtered)}** 筆。")
                else:
                     st.caption("📝 數據範圍：無交易紀錄符合篩選條件。")


            except Exception as e:
                st.error(f"現金流篩選發生錯誤：{e}")
                st.dataframe(df_D, use_container_width=True)
        else:
            st.warning("請確保 '表D_現金流' 包含 '淨收／支出'、'動作' 和 **'日期'** 欄位。")

    else:
        st.warning('現金流數據載入失敗，請檢查 "表D_現金流"。')


with tab2:
    # 🎯 已實現損益表格篩選與統計 - 優化為複選 + 快速按鈕
    if not df_E.empty:
        st.subheader('已實現損益 (表E_已實現損益)')
        
        df_E_clean = df_E.copy()
        
        # 檢查必要欄位
        if '已實現損益' in df_E_clean.columns and '股票' in df_E_clean.columns:
            try:
                # 數據轉換
                df_E_clean['已實現損益'] = pd.to_numeric(df_E_clean['已實現損益'], errors='coerce').fillna(0)
                df_E_clean['投資成本'] = pd.to_numeric(df_E_clean['投資成本'], errors='coerce').fillna(0)
                df_E_clean['帳面收入'] = pd.to_numeric(df_E_clean['帳面收入'], errors='coerce').fillna(0)
                df_E_clean['成交均價'] = pd.to_numeric(df_E_clean['成交均價'], errors='coerce').fillna(0)
                df_E_clean['成交股數'] = pd.to_numeric(df_E_clean['成交股數'], errors='coerce').fillna(0)

                date_col_name = None
                for col in df_E_clean.columns:
                    if '日期' in col: 
                        date_col_name = col
                        break

                if date_col_name:
                    df_E_clean[date_col_name] = pd.to_datetime(df_E_clean[date_col_name], errors='coerce')
                    df_E_clean = df_E_clean.sort_values(by=date_col_name, ascending=False)
                
                # 篩選器
                all_stocks = df_E_clean['股票'].astype(str).unique().tolist()
                
                if 'pnl_filter' not in st.session_state:
                    st.session_state['pnl_filter'] = all_stocks 

                # 🎯 按鈕與 Multiselect 布局
                col_multiselect, col_btn_all, col_btn_none = st.columns([4, 1, 1])
                
                with col_multiselect:
                    st.markdown("##### 篩選股票 (可多選，支援搜尋)")
                
                with col_multiselect:
                    selected_stocks = st.multiselect(
                        'Pnl Filter',
                        options=all_stocks, 
                        key='pnl_filter',
                        label_visibility="collapsed"
                    )
                    
                with col_btn_all:
                    if st.button("全選", key='btn_pnl_all'):
                        st.session_state['pnl_filter'] = all_stocks
                        st.rerun()

                with col_btn_none:
                    if st.button("清除篩選", key='btn_pnl_none'):
                        st.session_state['pnl_filter'] = [] 
                        st.rerun()

                df_E_filtered = df_E_clean[df_E_clean['股票'].isin(st.session_state['pnl_filter'])] if st.session_state['pnl_filter'] else pd.DataFrame()
                    
                total_pnl = df_E_filtered['已實現損益'].sum()
                
                # 顯示統計數據
                pnl_col1, pnl_col2 = st.columns(2)
                with pnl_col1:
                    st.metric(
                        label="🎯 總實現報酬 (元)", 
                        value=f"{total_pnl:,.2f}",
                        delta=f"{(total_pnl / 10000):,.2f} 萬",
                        delta_color="off"
                    )
                
                with pnl_col2:
                    st.markdown(f"**總交易筆數：** {len(df_E_filtered)}")

                # 🎯 表格顯示與格式化
                st.dataframe(
                    df_E_filtered.style.format({
                        date_col_name: DATE_FORMAT,
                        '已實現損益': CURRENCY_FORMAT,
                        '投資成本': CURRENCY_FORMAT,
                        '帳面收入': CURRENCY_FORMAT,
                        '成交均價': '{:,.2f}',
                        '成交股數': '{:,.0f}',
                    }), 
                    use_container_width=True, 
                    hide_index=True,
                    height=300 
                )
                
                # 🎯 底部標註
                if not df_E_filtered.empty and date_col_name:
                    valid_dates = df_E_filtered[date_col_name].dropna()
                    date_min = valid_dates.min() if not valid_dates.empty else 'N/A'
                    date_max = valid_dates.max() if not valid_dates.empty else 'N/A'
                    
                    date_min_str = date_min.strftime('%Y-%m-%d') if isinstance(date_min, datetime) else date_min
                    date_max_str = date_max.strftime('%Y-%m-%d') if isinstance(date_max, datetime) else date_max
                    
                    st.caption(f"📝 數據範圍：**{date_min_str}** ~ **{date_max_str}**，總筆數 **{len(df_E_filtered)}** 筆。")
                else:
                    st.caption("📝 數據範圍：無交易紀錄符合篩選條件。")


            except Exception as e:
                st.error(f"已實現損益篩選發生錯誤：{e}")
                st.dataframe(df_E, use_container_width=True)
        else:
            st.warning("請確保 '表E_已實現損益' 包含 '已實現損益' 和 '股票' 欄位。")
        
    else:
        st.warning('已實現損益數據載入失敗，請檢查 "表E_已實現損益"。')


with tab3:
    if not df_F.empty and '日期' in df_F.columns and '實質NAV' in df_F.columns:
        st.subheader('每日淨值 (表F_每日淨值)')
        try:
            df_F_cleaned = df_F.copy()
            
            # 數據轉換
            df_F_cleaned['日期'] = pd.to_datetime(df_F_cleaned['日期'], errors='coerce')
            df_F_cleaned['實質NAV'] = pd.to_numeric(df_F_cleaned['實質NAV'], errors='coerce')
            df_F_cleaned['股票市值'] = pd.to_numeric(df_F_cleaned['股票市值'], errors='coerce')
            df_F_cleaned['現金'] = pd.to_numeric(df_F_cleaned['現金'], errors='coerce')
            
            # 排序：依日期由新到舊 (用於表格顯示)
            df_F_cleaned = df_F_cleaned.sort_values(by='日期', ascending=False)

            # 繪製折線圖 (圖表需按日期升序排列)
            df_F_chart = df_F_cleaned.sort_values(by='日期', ascending=True)
            fig_nav = px.line(
                df_F_chart.dropna(subset=['日期', '實質NAV']), 
                x='日期', 
                y='實質NAV', 
                title='📈 實質淨資產價值 (NAV) 趨勢'
            )
            st.plotly_chart(fig_nav, use_container_width=True)
            
            # 🎯 在圖表下方新增數據表格
            with st.expander('查看每日淨值詳細數據', expanded=False):
                cols_to_display = ['日期', '實質NAV', '股票市值', '現金', '槓桿倍數β']
                
                df_subset = df_F_cleaned.loc[:, df_F_cleaned.columns.isin(cols_to_display)]
                if df_subset.empty:
                     df_subset = df_F
                     
                # 🎯 表格顯示與格式化
                st.dataframe(
                    df_subset.style.format({
                        '日期': DATE_FORMAT,
                        '實質NAV': CURRENCY_FORMAT,
                        '股票市值': CURRENCY_FORMAT,
                        '現金': CURRENCY_FORMAT,
                        '槓桿倍數β': lambda x: f"{pd.to_numeric(x, errors='coerce'):.2f}" if pd.notnull(x) and pd.to_numeric(x, errors='coerce') is not None else str(x),
                    }), 
                    use_container_width=True,
                    height=300 
                )
                
                # 🎯 底部標註
                if not df_subset.empty:
                    valid_dates = df_subset['日期'].dropna()
                    date_min = valid_dates.min() if not valid_dates.empty else 'N/A'
                    date_max = valid_dates.max() if not valid_dates.empty else 'N/A'
                    
                    date_min_str = date_min.strftime('%Y-%m-%d') if isinstance(date_min, datetime) else date_min
                    date_max_str = date_max.strftime('%Y-%m-%d') if isinstance(date_max, datetime) else date_max
                    
                    st.caption(f"📝 數據範圍：**{date_min_str}** ~ **{date_max_str}**，共 **{len(df_subset)}** 筆歷史紀錄。")
                else:
                    st.caption("📝 數據範圍：無歷史淨值紀錄。")

            
        except Exception as e:
            # 🎯 關鍵修正：將錯誤輸出，幫助您診斷是哪個欄位轉換失敗
            st.warning(f'無法繪製每日淨值圖或顯示表格，請檢查 "表F_每日淨值" 數據格式。錯誤: {e}')
    else:
        st.warning('每日淨值數據載入失敗，請檢查 "表F_每日淨值"。')
