import streamlit as st
import pandas as pd
import plotly.express as px
import gspread 

# 設置頁面配置，使用寬佈局以容納更多數據
st.set_page_config(layout="wide")

# 🎯 修正：注入自訂 CSS 來增大整體文字和標題大小，提升可讀性。
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
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🎯 步驟 1：請務必替換成您 Google Sheets 的【完整網址】
# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 
# ==============================================================================


# 數據載入函式 (已包含所有連線錯誤處理、快取和欄位名稱重複修正)
@st.cache_data(ttl="10m") 
def load_data(sheet_name): 
    # 使用 st.spinner 自動管理載入狀態，乾淨美觀
    with st.spinner(f"正在載入工作表: '{sheet_name}'..."):

        try:
            # --- 1. Secrets 認證準備 ---
            if "gsheets" not in st.secrets.get("connections", {}):
                st.error("Secrets 錯誤：找不到 [connections.gsheets] 區塊。請檢查您的 Streamlit Cloud Secrets 配置。")
                return pd.DataFrame()
            
            secrets_config = st.secrets["connections"]["gsheets"]
            if SHEET_URL == "YOUR_SPREADSHEET_URL_HERE":
                st.error("❌ 程式碼錯誤：請先將 SHEET_URL 替換為您的 Google Sheets 完整網址！")
                return pd.DataFrame()

            credentials_info = dict(secrets_config) 
            credentials_info["private_key"] = credentials_info["private_key"].replace('\\n', '\n')
            
            # --- 2. 連線與數據獲取 ---
            gc = gspread.service_account_from_dict(credentials_info)
            spreadsheet = gc.open_by_url(SHEET_URL)
            worksheet = spreadsheet.worksheet(sheet_name) 
            
            data = worksheet.get_all_values() 
            df = pd.DataFrame(data[1:], columns=data[0])
            
            # 🎯 修正重複欄位名稱 (針對表G等複雜表頭導致的 PyArrow 錯誤)
            if len(df.columns) != len(set(df.columns)):
                new_cols = []
                seen = {}
                for col in df.columns:
                    # 將空字串替換為 'Unnamed' (或任何非空的名稱)
                    clean_col = "Unnamed" if col == "" else col
                    
                    # 處理重複的名稱
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
        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f'GSheets 連線失敗！找不到試算表。請檢查 SHEET_URL 是否正確。')
            return pd.DataFrame()
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"GSheets 連線失敗！找不到工作表 '{sheet_name}'。請檢查名稱是否完全正確。")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"⚠️ 讀取工作表 '{sheet_name}' 發生未知錯誤。")
            st.exception(e) 
            return pd.DataFrame() 

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
# 1. 投資總覽 (核心總覽表格 + 風險指標燈號)
# ---------------------------------------------------
st.header('1. 投資總覽') 
if not df_C.empty:
    
    df_C_display = df_C.copy()
    
    # 🎯 欄位處理：確保索引設置和欄位名稱唯一性 (解決 ValueError)
    # 1. 使用第一欄（項目）作為新索引
    df_C_display.set_index(df_C_display.columns[0], inplace=True)
    
    # 2. 將剩下的唯一一欄（數值）重新命名為 '數值'
    if df_C_display.columns.size > 0:
        df_C_display.rename(columns={df_C_display.columns[0]: '數值'}, inplace=True)
        series_C = df_C_display['數值']
    else:
        # 處理只有一欄時的情況
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
    
    # 左側：顯示總覽數據 (確保表格樣式)
    with col_summary:
        st.subheader('核心資產數據')
        
        # 排除掉單獨作為指標顯示的行
        df_display = df_C_display[~df_C_display.index.isin(['β風險燈號', '槓桿倍數β'])].reset_index()
        
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
        # 💡 調整字體大小：將 h4 改為 h3，並增加 padding，使其更顯眼。
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
        
else:
    st.warning('總覽數據載入失敗，請檢查 "表C_總覽"。')

# ---------------------------------------------------
# 2. 持股分析與比例圖
# ---------------------------------------------------
st.header('2. 持股分析')
col_data, col_chart = st.columns([1, 1])

with col_data:
    if not df_A.empty:
        with st.expander('持股總表 (表A_持股總表)', expanded=True):
            st.dataframe(df_A, use_container_width=True)

with col_chart:
    if not df_B.empty and '市值（元）' in df_B.columns and '股票' in df_B.columns:
        try:
            df_B['市值（元）'] = pd.to_numeric(df_B['市值（元）'], errors='coerce')
            df_chart = df_B[df_B['市值（元）'] > 0]
            
            if not df_chart.empty:
                fig = px.pie(
                    df_chart, 
                    values='市值（元）', 
                    names='股票', 
                    title='📊 投資組合比例'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning('無有效數據可繪製比例圖。')
        except Exception:
            st.warning('無法產生持股比例圖，請檢查 "表B_持股比例" 數據格式。')
    else:
        st.warning('持股比例數據載入失敗，無法繪圖。')


# ---------------------------------------------------
# 3. 交易紀錄與淨值追蹤
# ---------------------------------------------------
st.header('3. 交易紀錄與淨值追蹤')

# 步驟：定義分頁 Tab
tab1, tab2, tab3 = st.tabs(['現金流', '已實現損益', '每日淨值'])

with tab1:
    if not df_D.empty:
        st.subheader('現金流紀錄 (表D_現金流)')
        st.dataframe(df_D, use_container_width=True)
    else:
        st.warning('現金流數據載入失敗，請檢查 "表D_現金流"。')

with tab2:
    if not df_E.empty:
        st.subheader('已實現損益 (表E_已實現損益)')
        st.dataframe(df_E, use_container_width=True)
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
# 4. 財富藍圖
# ---------------------------------------------------
if not df_G.empty:
    with st.expander('4. 財富藍圖 (表G_財富藍圖)', expanded=False):
        st.dataframe(df_G, use_container_width=True)
