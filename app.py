import streamlit as st
import pandas as pd
import plotly.express as px
import gspread # 使用 gspread 直接連線 Google Sheets

# 設置頁面配置
st.set_page_config(layout="wide")

# ==============================================================================
# 🎯 步驟 1：請務必替換成您 Google Sheets 的【完整網址】
# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 
# ==============================================================================


# 使用 gspread 進行連線和數據讀取，並加入數據快取
@st.cache_data(ttl="10m") 
def load_data(sheet_name): 
    # 在嘗試連線前顯示一個狀態訊息
    st.info(f"正在嘗試連線並載入工作表: '{sheet_name}'...") 

    try:
        # --- 1. 從 Streamlit Secrets 中讀取金鑰並進行格式處理 ---
        
        # 檢查 Secrets 區塊是否存在
        if "gsheets" not in st.secrets.get("connections", {}):
            st.error("Secrets 錯誤：找不到 [connections.gsheets] 區塊。請檢查您的 Streamlit Cloud Secrets 配置。")
            return pd.DataFrame()
        
        secrets_config = st.secrets["connections"]["gsheets"]
        
        # 檢查 SHEET_URL 是否已替換 (這是一個額外的安全檢查)
        if SHEET_URL == "YOUR_SPREADSHEET_URL_HERE":
            st.error("❌ 程式碼錯誤：請先將 SHEET_URL 替換為您的 Google Sheets 完整網址！")
            return pd.DataFrame()

        # 【關鍵修正】複製一份配置，以便進行修改 (dict() 確保我們有一個可寫的副本)
        credentials_info = dict(secrets_config) 
        
        # 修正 private_key 中的換行符號。
        credentials_info["private_key"] = credentials_info["private_key"].replace('\\n', '\n')
        
        # --- 2. 使用 gspread 認證 ---
        gc = gspread.service_account_from_dict(credentials_info)
        
        # --- 3. 打開試算表和工作表 ---
        spreadsheet = gc.open_by_url(SHEET_URL)
        worksheet = spreadsheet.worksheet(sheet_name) 
        
        # 取得所有數據，第一行為欄位標頭
        data = worksheet.get_all_values() 
        
        # 轉換為 DataFrame
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

        # 執行資料清理 (將 NaN 替換為 0)
        df = df.fillna(0)
        
        # 成功載入後移除狀態訊息
        st.empty() 
        return df
    
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"GSheets 連線失敗！找不到試算表。請檢查 SHEET_URL 是否正確，並確保金鑰已授予權限。")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"GSheets 連線失敗！找不到工作表 '{sheet_name}'。請檢查工作表名稱是否完全正確。")
        return pd.DataFrame()
    except Exception as e:
        # 🚨 關鍵改變：強制顯示詳細錯誤追蹤
        st.error(f"⚠️ 讀取工作表 '{sheet_name}' 發生未知錯誤。請檢查 Secrets 配置細節或網路連線。")
        st.exception(e) 
        return pd.DataFrame()

# --- 應用程式主體開始 ---

st.title("💰 投資組合儀表板")

# 🎯 步驟 2：載入所有需要的數據 (請確保這些名稱與您的 Google Sheets 分頁名稱完全一致)
df_A = load_data("表A_持股總表")
df_B = load_data("表B_持股比例")
df_C = load_data("表C_總覽")
df_D = load_data("表D_現金流")
df_E = load_data("表E_已實現損益")
df_F = load_data("表F_每日淨值")
df_G = load_data("表G_財富藍圖")


# --- 1. 投資總覽 (使用 df_C) ---
st.header("1. 投資總覽") 
if not df_C.empty:
    st.dataframe(df_C, use_container_width=True, hide_index=True)
else:
    st.warning("總覽數據載入失敗，請檢查 '表C_總覽'。")


# --- 2. 持股分析與比例圖 (使用 df_A 和 df_B) ---
st.header("2. 持股分析")
col_data, col_chart = st.columns([1, 1])

with col_data:
    if not df_A.empty:
        with st.expander("持股總表 (表A_持股總表)", expanded=True):
            st.dataframe(df_A, use_container_width=True)

with col_chart:
    if not df_B.empty and '市值（元）' in df_B.columns and '股票' in df_B.columns:
        try:
            # 繪製圓餅圖 (使用表B的數據)
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


# --- 3. 交易紀錄與淨值追蹤 (使用 df_D, df_E, df_F) ---
st.header("3. 交易紀錄與淨值追蹤")

tab1, tab2, tab3 = st.tabs(["現金流", "已實現損益", "每日淨值"])

with tab1:
    if not df_D.empty:
        st.subheader("現金流紀錄 (表D_現金流)")
        st.dataframe(df_D, use_container_width=True)
    else:
        st.warning("現金流數據載入失敗，請檢查 '表D_現金流'。")

with tab2:
    if not df_E.empty:
        st.subheader("已實現損益 (表E_已實現損益)")
        st.dataframe(df_E, use_container_width=True)
    else:
        st.warning("已實現損益數據載入失敗，請檢查 '表E_已實現損益'。")

with tab3:
    if not df_F.empty and '日期' in df_F.columns and '實質NAV' in df_F.columns:
        st.subheader("每日淨值 (表F_每日淨值)")
        try:
            # 確保數據類型正確以便繪圖
            df_F['日期'] = pd.to_datetime(df_F['日期'], errors='coerce')
            df_F['實質NAV'] = pd.to_numeric(df_F['實質NAV'], errors='coerce')
            
            fig_nav = px.line(
                df_F.dropna(subset=['日期', '實質NAV']), 
                x='日期', 
                y='實質NAV', 
                title='📈 實質淨資產價值 (NAV) 趨勢'
            )
            st.plotly_chart(fig_nav, use_container_width=True)
        except Exception:
            st.warning("無法繪製每日淨值圖，請檢查 '表F_每日淨值' 數據格式。")
    else:
        st.warning("每日淨值數據載入失敗，請檢查 '表F_每日淨值'。")


st.markdown("---")
if not df_G.empty:
    with st.expander("4. 財富藍圖 (表G_財富藍圖)", expanded=False):
        st.dataframe(df_G, use_container_width=True)

