import streamlit as st
import pandas as pd
import plotly.express as px
import gspread 
from datetime import datetime
import yfinance as yf # 🎯 用於獲取股票價格
import time # 用於處理 yfinance 的限速

# 設置頁面配置，使用寬佈局以容納更多數據
st.set_page_config(layout="wide")

# 🎯 注入自訂 CSS 來增大整體文字和標題大小
st.markdown("""
<style>
/* 增加應用程式的基礎字體大小 */
html, body, [class*="stApp"] {
    font-size: 16px; 
}
/* 增加標題 (Header) 的字體大小 */
h1 { font-size: 2.5em; } 
h2 { font-size: 1.8em; } /* 針對 st.header() */
h3 { font-size: 1.5em; } /* 針對 st.subheader() */

/* 增加 Streamlit 內建數據表格的文字大小 */
.stDataFrame {
    font-size: 1.0em; 
}

/* 針對 st.metric 的標籤和數值進行放大 */
.stMetric > div:first-child {
    font-size: 1.25em !important; /* Metric label 標籤 */
}
.stMetric > div:nth-child(2) > div:first-child {
    font-size: 2.5em !important; /* Metric value 數值 */
}

/* 🎯 修正 2: 移除多餘的 margin-top，讓按鈕與 Multiselect 底部對齊 */
.stButton>button {
    width: 100%;
    margin-top: 0px; 
}

/* 隱藏 Multiselect 的標籤 (在 HTML 級別隱藏，配合 label_visibility="collapsed" 使用) */
div[data-testid="stMultiSelect"] > label {
    display: none; 
}

/* 讓 Multiselect 和按鈕在同一行時，能有緊密的空間感 */
/* 由於 Streamlit 的 flex 佈局，將按鈕的垂直間距移除是關鍵 */
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🎯 步驟 1：請務必替換成您 Google Sheets 的【完整網址】
# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 
# ==============================================================================


# 初始化 Session State 來儲存即時價格
if 'live_prices' not in st.session_state:
    st.session_state['live_prices'] = {} # {ticker: price}


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


# 數據載入函式 (僅用於讀取)
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
            
            # 修正重複欄位名稱
            if len(df.columns) != len(set(df.columns)):
                new_cols = []
                seen = {}
                for col in df.columns:
                    clean_col = "Unnamed" if col == "" else col
                    if clean_col in seen:
                        seen[clean_col] += 1
                        new_cols.append(f"{clean_col}_{seen[clean_col]}")
                    else:
                        seen[clean_col] = 0
                        new_cols.append(clean_col)
                df.columns = new_cols

            df = df.fillna(0)
            return df
        
        # --- 錯誤處理 ---
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"GSheets 連線失敗：找不到工作表 '{sheet_name}'。請檢查名稱是否完全正確。")
            return pd.DataFrame()
        except Exception as e:
            # 已經在 get_gsheet_connection 處理了連線錯誤，這裡主要處理工作表錯誤
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


# 🎯 新增寫入函式
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
            write_values.append([f"{price:,.2f}"]) # 格式化為字串，保留兩位小數並加上千分位
        else:
            write_values.append(['']) # 未找到價格則留空

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

# 🎯 數值清潔函式 (修正: 移除所有非數字和非小數點的字元)
def clean_numeric_string(s):
    """移除所有非數字、非小數點、非負號的字元，以便於轉換為 float。"""
    if pd.isna(s) or s is None:
        return None
        
    s = str(s).strip()
    
    # 將所有非 (數字, 負號, 小數點) 的字元替換為空字串
    # 注意：這裡假設 Sheets 中的數字是以點 '.' 作為小數點
    import re
    cleaned_s = re.sub(r'[^\d.-]', '', s) 

    # 處理多個負號或多個小數點的情況
    if cleaned_s.count('-') > 1 or cleaned_s.count('.') > 1:
        # 如果格式異常，則返回 None 讓 pd.to_numeric 處理
        return None
    
    return cleaned_s if cleaned_s else None

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

# ---------------------------------------------------
# 0. 股價即時更新區塊 (位於側邊欄)
# ---------------------------------------------------
st.sidebar.header("🎯 股價數據管理")

# 🎯 修正按鈕文字和邏輯
if st.sidebar.button("💾 獲取即時價格並寫入 Sheets", type="primary"):
    if df_A.empty or '股票' not in df_A.columns:
        st.sidebar.error("❌ '表A_持股總表' 數據不完整或沒有 '股票' 欄位。")
    else:
        # 獲取所有唯一的股票代碼，並過濾掉空值
        tickers = df_A['股票'].astype(str).str.strip().unique()
        valid_tickers = [t for t in tickers if t]
        
        if not valid_tickers:
            st.sidebar.warning("工作表中沒有找到有效的股票代碼。")
        else:
            # 步驟 1: 呼叫新的獲取價格函式
            price_updates = fetch_current_prices(valid_tickers)
            st.session_state['live_prices'] = price_updates # 更新 session state 供儀表板即時顯示
            
            if price_updates:
                # 步驟 2: 將價格寫回 Google Sheets
                if write_prices_to_sheet(df_A, price_updates):
                    st.sidebar.success(f"🎉 成功寫入 {len(price_updates)} 筆最新價格到 Sheets！")
                    # 步驟 3: 清除 load_data 快取並重新載入頁面
                    load_data.clear()
                    st.rerun() 
                else:
                    st.sidebar.error("❌ 寫入 Google Sheets 失敗，請檢查連線配置。")

            else:
                st.sidebar.warning("獲取價格失敗，未進行寫入。請檢查股票代碼。")
            
st.sidebar.caption("💡 點擊此按鈕，價格會寫入 Google Sheets 的 E 欄。")
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
    risk_level = str(series_C.get('β風險燈號', 'N/A'))
    leverage = str(series_C.get('槓桿倍數β', 'N/A'))

    # 風險等級顏色判斷
    if '安全' in risk_level:
        color = 'green'
        emoji = '✅'
    elif '警戒' in risk_level:
        color = 'orange'
        emoji = '⚠️'
    elif '危險' in risk_level:
        color = 'red'
        emoji = '🚨'
    else:
        color = 'gray'
        emoji = '❓'

    col_summary, col_indicators = st.columns([2, 1])
    
    # 左側：顯示總覽數據 
    with col_summary:
        st.subheader('核心資產數據')
        
        # 排除掉單獨作為指標顯示的行，以及用於目標追蹤的行
        exclude_cols = ['β風險燈號', '槓桿倍數β', '短期財務目標', '短期財務目標差距', '達成進度']
        df_display = df_C_display[~df_C_display.index.isin(exclude_cols)].reset_index()
        
        # 確保最終欄位名稱是 ['項目', '數值']
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
            f"<h3 style='text-align: center; color: white; background-color: {color}; border: 2px solid {color}; padding: 15px; border-radius: 8px; font-weight: bold;'>"
            f"{emoji} {risk_level}"
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
        
        # 🎯 目標進度表 (表C_總覽) - 修正讀取問題
        st.subheader('🎯 財富目標進度')
        
        target_name_key = '短期財務目標'
        gap_name_key = '短期財務目標差距'

        # 🎯 步驟 1: 提取原始值
        target_value_raw = series_C.get(target_name_key)
        gap_value_raw = series_C.get(gap_name_key)
        
        # 🎯 步驟 2: 清潔字串並轉換為數字 (解決Sheets公式格式化問題)
        cleaned_target_raw = clean_numeric_string(target_value_raw)
        cleaned_gap_raw = clean_numeric_string(gap_value_raw)
        
        target = pd.to_numeric(cleaned_target_raw, errors='coerce')
        gap = pd.to_numeric(cleaned_gap_raw, errors='coerce')
        
        # 僅在兩個值都是有效數字且目標大於0時顯示進度條
        if not pd.isna(target) and not pd.isna(gap) and target > 0:
            current = target - gap
            percent_achieved = (current / target)
            display_percent = min(100, round(percent_achieved * 100, 2)) # 🎯 修正 1: 進度顯示保留兩位小數
            
            st.markdown(f"**{target_name_key}** ({display_percent:.2f}%)")
            st.progress(min(1.0, percent_achieved)) # st.progress 接受 0.0 到 1.0
            st.caption(f"目前累積: {current:,.0f} / 目標: {target:,.0f} (差距: {gap:,.0f})")
            
            # 顯示達成進度的數值（如果存在於 C 表中）
            progress_val = series_C.get('達成進度')
            if progress_val:
                st.caption(f"Sheets 中計算的達成進度: {progress_val}")
                
        else:
            # 增強錯誤提示：確認實際存在哪些 key
            missing_info = []
            if pd.isna(target) or target <= 0:
                missing_info.append(f"'{target_name_key}' (Target Value: {target_value_raw} -> Cleaned: {cleaned_target_raw})")
            if pd.isna(gap):
                missing_info.append(f"'{gap_name_key}' (Gap Value: {gap_value_raw} -> Cleaned: {cleaned_gap_raw})")
                
            if missing_info:
                st.caption(f"⚠️ **無法計算進度：** 請檢查 '表C_總覽' 中以下項目的原始數值是否正確（例如有無中文符號或千分位符號未被正確清除）。")
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
        
        # 🎯 檢查 Session State 中是否有最新的即時價格
        # 如果使用者點擊了寫入按鈕，live_prices 會被更新，並在此顯示
        if st.session_state['live_prices']:
            df_display['即時收盤價'] = df_display['股票'].astype(str).str.strip().map(st.session_state['live_prices']).fillna('')
            
            # 將新的欄位移到前面，提高可見度
            cols = ['即時收盤價'] + [col for col in df_display.columns if col != '即時收盤價']
            df_display = df_display[cols]
            
        with st.expander('持股總表 (表A_持股總表)', expanded=True):
            st.dataframe(df_display, use_container_width=True)

with col_chart:
    if not df_B.empty and '市值（元）' in df_B.columns and '股票' in df_B.columns:
        try:
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
        
        if '淨收／支出' in df_D_clean.columns and '動作' in df_D_clean.columns:
            try:
                # 數據清洗：將金額轉換為數字
                df_D_clean['淨收／支出'] = pd.to_numeric(df_D_clean['淨收／支出'], errors='coerce').fillna(0)
                
                # 篩選器
                available_categories = df_D_clean['動作'].astype(str).unique().tolist()
                
                # 修正: 將預設選項設為所有類別 (全選)
                selected_categories = st.multiselect(
                    '篩選動作 (預設全選)', 
                    options=available_categories, 
                    default=available_categories, # 預設為全選
                    key='cashflow_filter'
                )
                
                # 執行篩選
                if selected_categories:
                    df_D_filtered = df_D_clean[df_D_clean['動作'].isin(selected_categories)] 
                else:
                    df_D_filtered = pd.DataFrame() 
                    
                # 總計計算
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
                
                # 顯示篩選後的表格 (包含 用途／股票 欄位)
                st.dataframe(df_D_filtered, use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"現金流篩選發生錯誤：{e}")
                st.dataframe(df_D, use_container_width=True)
        else:
            st.warning("請確保 '表D_現金流' 包含 '淨收／支出' 和 '動作' 欄位。")

    else:
        st.warning('現金流數據載入失敗，請檢查 "表D_現金流"。')


with tab2:
    # 🎯 已實現損益表格篩選與統計 - 優化為複選 + 快速按鈕
    if not df_E.empty:
        st.subheader('已實現損益 (表E_已實現損益)')
        
        df_E_clean = df_E.copy()
        
        if '已實現損益' in df_E_clean.columns and '股票' in df_E_clean.columns:
            try:
                # 數據清洗：將損益欄位轉換為數字
                df_E_clean['已實現損益'] = pd.to_numeric(df_E_clean['已實現損益'], errors='coerce').fillna(0)
                
                # 篩選器
                all_stocks = df_E_clean['股票'].astype(str).unique().tolist()
                
                # 🎯 步驟 1: 初始化 session state，確保預設為全選
                if 'pnl_filter' not in st.session_state:
                    st.session_state['pnl_filter'] = all_stocks 

                # 🎯 步驟 2: 配置 multiselect 及其快速控制按鈕 (修正按鈕位置)
                # 分成三欄：標籤 (4/6)、全選按鈕 (1)、清除按鈕 (1)
                col_multiselect, col_btn_all, col_btn_none = st.columns([4, 1, 1])
                
                # 使用 markdown 作為標籤
                with col_multiselect:
                    st.markdown("##### 篩選股票 (可多選，支援搜尋)")
                
                # Multiselect 放在標籤欄位下方，並使用 label_visibility="collapsed" 確保緊湊
                with col_multiselect:
                    # Multiselect 透過 key='pnl_filter' 自動從 st.session_state['pnl_filter'] 讀取數值
                    selected_stocks = st.multiselect(
                        'Pnl Filter', # 雖然設置了 label，但使用 CSS 和 label_visibility 隱藏
                        options=all_stocks, 
                        key='pnl_filter',
                        label_visibility="collapsed" # 🎯 關鍵修正：隱藏標籤，避免佔用垂直空間
                    )
                    
                with col_btn_all:
                    if st.button("全選", key='btn_pnl_all'):
                        # 點擊後，設定 state 為所有股票，並重跑
                        st.session_state['pnl_filter'] = all_stocks
                        st.rerun()

                with col_btn_none:
                    if st.button("清除篩選", key='btn_pnl_none'):
                        # 點擊後，設定 state 為空列表，並重跑
                        st.session_state['pnl_filter'] = [] # 🎯 邏輯正確: 清除篩選=不選取任何股票
                        st.rerun()

                # 執行篩選
                if selected_stocks:
                    df_E_filtered = df_E_clean[df_E_clean['股票'].isin(selected_stocks)]
                else:
                    df_E_filtered = pd.DataFrame()
                    
                # 總報酬計算
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


                # 顯示篩選後的表格
                st.dataframe(df_E_filtered, use_container_width=True, hide_index=True)

            except Exception as e:
                # 🎯 將錯誤輸出到控制台，以便於調試
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
            df_F_cleaned['日期'] = pd.to_datetime(df_F_cleaned['日期'], errors='coerce')
            df_F_cleaned['實質NAV'] = pd.to_numeric(df_F_cleaned['實質NAV'], errors='coerce')
            
            # 繪製折線圖
            fig_nav = px.line(
                df_F_cleaned.dropna(subset=['日期', '實質NAV']), 
                x='日期', 
                y='實質NAV', 
                title='📈 實質淨資產價值 (NAV) 趨勢'
            )
            st.plotly_chart(fig_nav, use_container_width=True)
            
            # 在圖表下方新增數據表格
            with st.expander('查看每日淨值詳細數據', expanded=False):
                # 僅顯示需要的欄位，避免過多欄位擠壓顯示空間
                cols_to_display = ['日期', '實質NAV', '股票市值', '現金', '槓桿倍數β']
                
                # 過濾並確保欄位存在，否則顯示全部
                df_subset = df_F_cleaned.loc[:, df_F_cleaned.columns.isin(cols_to_display)]
                if df_subset.empty:
                     df_subset = df_F
                     
                st.dataframe(df_subset, use_container_width=True)
            
        except Exception:
            st.warning('無法繪製每日淨值圖，請檢查 "表F_每日淨值" 數據格式。')
    else:
        st.warning('每日淨值數據載入失敗，請檢查 "表F_每日淨值"。')


st.markdown('---')

# ---------------------------------------------------
# 4. 資料輸入與管理 (僅保留財富藍圖的展示)
# ---------------------------------------------------
st.header('4. 資料管理')

# 使用 Tab 來分開不同的輸入類型
tab_blueprint = st.tabs(['財富藍圖 (表G)'])[0] 

with tab_blueprint:
    if not df_G.empty:
        st.subheader('財富藍圖 (表G_財富藍圖)')
        st.caption('此表格數據來自 Google Sheets "表G_財富藍圖"。')
        st.dataframe(df_G, use_container_width=True)
        st.caption('💡 **注意:** 目標進度條目前是使用 **表C_總覽** 的數據來計算。')
    else:
        st.warning('財富藍圖數據載入失敗，請檢查 "表G_財富藍圖"。')

