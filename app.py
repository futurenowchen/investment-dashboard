import streamlit as st
import pandas as pd
import plotly.express as px
import gspread # 新增：用於直接連線 Google Sheets
import json # 新增：用於處理金鑰文件

# 設置頁面配置
st.set_page_config(layout="wide")

# ==============================================================================
# 請務必替換成您 Google Sheets 的【完整網址】
# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 
# 您的工作表名稱
SHEET_NAME = "七表_GSheets線上維護版" 
# ==============================================================================


# 使用 gspread 進行連線和數據讀取
@st.cache_data(ttl="10m") # 設置快取時間為 10 分鐘
def load_data():
    if SHEET_URL == "YOUR_SPREADSHEET_URL_HERE":
        st.error("❌ 請先將代碼中的 SHEET_URL 替換為您的 Google Sheets 完整網址！")
        return pd.DataFrame()

    try:
        # --- 1. 從 Streamlit Secrets 中讀取金鑰並進行格式處理 ---
        
        # 檢查 Secrets 區塊
        if "gsheets" not in st.secrets.get("connections", {}):
            st.error("Secrets 錯誤：找不到 [connections.gsheets] 區塊。請檢查您的 Streamlit Cloud Secrets 配置。")
            return pd.DataFrame()
        
        # 從 Secrets 讀取金鑰配置 (Secrets 物件是唯讀的)
        secrets_config = st.secrets["connections"]["gsheets"]
        
        # **【關鍵修正】**：複製一份配置，以便進行修改 (dict() 確保我們有一個可寫的副本)
        credentials_info = dict(secrets_config) 
        
        # 修正 private_key 中的換行符號。
        credentials_info["private_key"] = credentials_info["private_key"].replace('\\n', '\n')
        
        # --- 2. 使用 gspread 認證 ---
        gc = gspread.service_account_from_dict(credentials_info)
        
        # --- 3. 打開試算表和工作表 ---
        spreadsheet = gc.open_by_url(SHEET_URL)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        
        # 取得所有數據，第一行為欄位標頭
        data = worksheet.get_all_values() 
        
        # 轉換為 DataFrame
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # 執行資料清理 (將 NaN 替換為 0)
        df = df.fillna(0)
        return df
    
    # 這裡可以加入更詳細的 gspread 異常處理
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("GSheets 連線錯誤：找不到該試算表。請檢查 URL 是否正確，並確保金鑰有權限。")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"GSheets 連線錯誤：找不到工作表 '{SHEET_NAME}'。請檢查工作表名稱是否正確。")
        return pd.DataFrame()
    except Exception as e:
        # 捕捉所有其他錯誤
        st.error(f"⚠️ 數據讀取失敗！請檢查您的 Secrets 配置細節是否與 JSON 金鑰檔案完全吻合。")
        st.exception(e) 
        return pd.DataFrame() 

# --- 應用程式主體開始 ---

st.title("💰 投資組合儀表板")

df_holdings = load_data()

if not df_holdings.empty:
    st.header(f"1. 持股總表 (來自工作表：{SHEET_NAME})")
    st.dataframe(df_holdings, use_container_width=True)

    # 範例：根據您的數據結構繪製持股比例圖
    if '市值（元）' in df_holdings.columns and '股票' in df_holdings.columns:
        try:
            # 確保 '市值（元）' 是數字類型
            df_holdings['市值（元）'] = pd.to_numeric(df_holdings['市值（元）'], errors='coerce')
            
            # 過濾市值為 0 的項目
            df_chart = df_holdings[df_holdings['市值（元）'] > 0]
            
            if not df_chart.empty:
                fig = px.pie(
                    df_chart, 
                    values='市值（元）', 
                    names='股票', 
                    title='📊 投資組合比例'
                )
                st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.warning("無法產生持股比例圖，請檢查數據欄位名稱和格式是否正確。")

    st.markdown("---")
    st.info("🎯 **您的其他分析和儀表板程式碼請繼續在下方加入**")

else:
    st.error("由於數據載入失敗，儀表板的分析部分無法顯示。請根據上方的錯誤訊息進行修正。")

