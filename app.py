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

    try:
        # --- 1. 從 Streamlit Secrets 中讀取金鑰並進行格式處理 ---
        
        # 檢查 Secrets 區塊是否存在
        if "gsheets" not in st.secrets.get("connections", {}):
            st.error("Secrets 錯誤：找不到 [connections.gsheets] 區塊。請檢查您的 Streamlit Cloud Secrets 配置。")
            return pd.DataFrame()
        
        # 從 Secrets 讀取金鑰配置 (Secrets 物件是唯讀的)
        secrets_config = st.secrets["connections"]["gsheets"]
        
        # 【關鍵修正】複製一份配置，以便進行修改 (dict() 確保我們有一個可寫的副本)
        credentials_info = dict(secrets_config) 
        
        # 修正 private_key 中的換行符號。
        credentials_info["private_key"] = credentials_info["private_key"].replace('\\n', '\n')
        
        # --- 2. 使用 gspread 認證 ---
        gc = gspread.service_account_from_dict(credentials_info)
        
        # --- 3. 打開試算表和工作表 ---
        spreadsheet = gc.open_by_url(SHEET_URL)
        # 使用傳入的 sheet_name 尋找工作表
        worksheet = spreadsheet.worksheet(sheet_name) 
        
        # 取得所有數據，第一行為欄位標頭
        data = worksheet.get_all_values() 
        
        # 轉換為 DataFrame
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # 執行資料清理 (將 NaN 替換為 0)
        df = df.fillna(0)
        return df
    
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"GSheets 連線錯誤：找不到試算表。請檢查 SHEET_URL 是否正確，並確保金鑰有權限。")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"GSheets 連線錯誤：找不到工作表 '{sheet_name}'。請檢查工作表名稱是否正確。")
        return pd.DataFrame()
    except Exception as e:
        # 捕捉所有其他錯誤，例如網路問題或金鑰格式仍有微小問題
        st.error(f"⚠️ 讀取工作表 '{sheet_name}' 失敗。請檢查您的 Secrets 配置細節或網路連線。")
        # st.exception(e) # 暫時註解，避免畫面過於混亂
        return pd.DataFrame() 

# --- 應用程式主體開始 ---

st.title("💰 投資組合儀表板")

# 🎯 步驟 2：載入所有需要的數據 (請確保這些名稱與您的 Google Sheets 分頁名稱完全一致)
df_A = load_data("表A_持股總表")
df_B = load_data("表B_持股比例")
df_C = load_data("表C_總覽")
df_D = load_data("表D_現金流")
df_E = load_data("表E_已實現損益")
df_F = load_data("表F_每日淨值") # 根據您的檔案清單，也加入這張表
df_G = load_data("表G_財富藍圖") # 根據您的檔案清單，也加入這張表


# --- 1. 投資總覽 (使用 df_C) ---
st.header("1.
