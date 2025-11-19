import streamlit as st
import pandas as pd
import plotly.express as px
import gspread 

# 設置頁面配置
st.set_page_config(layout="wide")

# ==============================================================================
# 🎯 步驟 1：請務必替換成您 Google Sheets 的【完整網址】
# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 
# ==============================================================================


# 使用 gspread 進行連線和數據讀取，並加入數據快取 (已修正所有錯誤)
@st.cache_data(ttl="10m") 
def load_data(sheet_name): 
    # 🎯 使用 st.spinner 自動管理載入狀態，乾淨美觀
    with st.spinner(f"正在載入工作表: '{sheet_name}'..."):

        try:
            # --- 1. 從 Streamlit Secrets 中讀取金鑰並進行格式處理 ---
            if "gsheets" not in st.secrets.get("connections", {}):
                st.error("Secrets 錯誤：找不到 [connections.gsheets] 區塊。")
                return pd.DataFrame()
            
            secrets_config = st.secrets["connections"]["gsheets"]
            if SHEET_URL == "YOUR_SPREADSHEET_URL_HERE":
                st.error("❌ 程式碼錯誤：請先將 SHEET_URL 替換為您的 Google Sheets 完整網址！")
                return pd.DataFrame()

            credentials_info = dict(secrets_config) 
            credentials_info["private_key"] = credentials_info["private_key"].replace('\\n', '\n')
            
            # --- 2. 使用 gspread 認證與連線 ---
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
        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f"GSheets 連線失敗！找不到試算表。")
            return pd.DataFrame()
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"GSheets 連線失敗！找不到工作表 '{sheet_name}'。")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"⚠️ 讀取工作表 '{sheet_name}' 發生未知錯誤。")
            st.exception(e) 
            return pd.DataFrame() 

# --- 應用程式主體開始 ---

st.title("💰 投資組合儀表板")

# 🎯 載入所有需要的數據
df_A = load_data("表A_持股總表")
df_B = load_data("表B_持股比例")
df_C = load_data("表C_總覽")
df_D = load_data("表D_現金流")
df_E = load_data("表E_已實現損益")
df_F = load_data("表F_每日淨值")
df_G = load_data("表G_財富藍圖")

# ----------------------------------------------------------------------
# 1. 投資總覽 (放大字體顯示，指標在旁邊)
# ----------------------------------------------------------------------
st.header("1. 投資總覽") 
if not df_C.empty:
    
    df_C_display = df_C.copy()
    
    # 🎯 關鍵修正：使用 set_index 確保欄位和索引分離，並明確命名
    # 1. 使用 df.columns[0] (即 '項目') 作為新索引，並將其從欄位中移除。
    df_C_display.set_index(df_C_display.columns[0], inplace=True)
    
    # 2. 將剩下的唯一一欄（數值）重新命名為 '數值'，以確保其名稱不是空字串或重複
    df_C_display.rename(columns={df_C_display.columns[0]: "數值"}, inplace=True)
    
    # 3. 提取 series
    series_C = df_C_display["數值"]

    # 提取關鍵值
    risk_level = series_C.get('β風險燈號', 'N/A')
    leverage = series_C.get('槓桿倍數β', 'N/A')

    # 風險等級顏色判斷
    if risk_level == "安全":
        color = "green"
        emoji = "✅"
    elif risk_level == "警戒":
        color = "orange"
        emoji = "⚠️"
    elif risk_level == "危險":
        color = "red"
        emoji = "🚨"
    else:
        color = "gray"
        emoji = "❓"

    col_summary, col_indicators = st.columns([2, 1])
    
    # 左側：顯示總覽數據 (確保表格樣式)
    with col_summary:
        st.subheader("核心資產數據")
        
        # 排除掉單獨作為指標顯示的行，讓表格更精簡
        df_display = df_C_display[~df_C_display.index.isin(['β風險燈號', '槓桿倍數β'])].reset_index()
        
        # 確保最終欄位名稱是 ['項目', '數值']，這是 reset_index 之後的標準名稱
        df_display.columns = ["項目", "數值"]

        st.dataframe(
            df_display, 
            use_container_width=True, 
            hide_index=True
        )

    # 右側：風險燈號和槓桿倍數 (保持視覺強化)
    with col_indicators:
        st.subheader("風險指標")
        
        # 風險燈號 (使用 HTML 嵌入方式放大字體和顏色)
        st.markdown(
            f"""
            <h4 style='text-align: center; color: white; background-color: {color}; border: 2px solid {color}; padding: 10px; border-radius: 5px;'>
                {emoji} {risk_level}
            </h4>
            """,
            unsafe_allow_html=True
        )

        # 槓桿倍數 (使用 st.metric 並搭配放大數值)
        # 安全轉換：確保 leverage 是數字才能格式化
        try:
            leverage_value = f"{float(leverage):.4f}"
        except ValueError:
            leverage_value = str(leverage)
            
        st.metric(
            label="槓桿倍數 β", 
            value=leverage_value, 
            delta_color="off"
        )
        
else:
    st.warning("總覽數據載入失敗，請檢查 '表C_總覽'。")

# ----------------------------------------------------------------------
# 2. 持股分析與比例圖
# ----------------------------------------------------------------------
st.header("2. 持股分析")
col_data, col_chart = st.columns([1, 1])

with col_data:
    if not df_A.empty:
        with st.expander("持股總表 (表A_持股總表)", expanded=True):
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
                st.warning("無有效數據可繪製比例圖。")
        except Exception:
            st.warning("無法產生持股比例圖，請檢查 '表B_持股比例' 數據格式。")
    else:
        st.warning("持股比例數據載入失敗，無法繪圖。")


with tab3:
    if not df_F.empty and '日期' in df_F.columns and '實質NAV' in df_F.columns:
        st.subheader("每日淨值 (表F_每日淨值)")
        try:
            df_F['日期'] = pd.to_datetime(df_F['日期'], errors='coerce')
            df_F['實質NAV'] = pd.to_numeric(df_F['實質NAV'], errors='coerce')
            
            # 繪製折線圖
            fig_nav = px.line(
                df_F.dropna(subset=['日期', '實質NAV']), 
                x='日期', 
                y='實質NAV', 
                title='📈 實質淨資產價值 (NAV) 趨勢'
            )
            st.plotly_chart(fig_nav, use_container_width=True)
            
            # 🎯 修正：在圖表下方新增數據表格
            with st.expander("查看每日淨值詳細數據", expanded=False):
                st.dataframe(df_F, use_container_width=True)
            
        except Exception:
            st.warning("無法繪製每日淨值圖，請檢查 '表F_每日淨值' 數據格式。")
    else:
        st.warning("每日淨值數據載入失敗，請檢查 '表F_每日淨值'。")
# ----------------------------------------------------------------------
# 4. 財富藍圖
# ----------------------------------------------------------------------
if not df_G.empty:
    with st.expander("4. 財富藍圖 (表G_財富藍圖)", expanded=False):
        st.dataframe(df_G, use_container_width=True)


