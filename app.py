import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
# import json # 此行可刪除

# 設置頁面配置
st.set_page_config(layout="wide")

# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" # <--- 請再次確認您已替換
# ==============================================================================


# 【重要】load_data 函式本身保持不變，但將 SHEET_NAME 作為參數傳入
@st.cache_data(ttl="10m") 
def load_data(sheet_name): # <--- 接收工作表名稱參數
    if SHEET_URL == "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit":
        st.error("❌ 請先將代碼中的 SHEET_URL 替換為您的 Google Sheets 完整網址！")
        return pd.DataFrame()

    try:
        # 讀取 Secrets 配置
        secrets_config = st.secrets["connections"]["gsheets"]
        credentials_info = dict(secrets_config) 
        credentials_info["private_key"] = credentials_info["private_key"].replace('\\n', '\n')
        
        # 認證
        gc = gspread.service_account_from_dict(credentials_info)
        
        # 打開試算表和工作表 (使用傳入的 sheet_name)
        spreadsheet = gc.open_by_url(SHEET_URL)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # 取得所有數據，第一行為欄位標頭
        data = worksheet.get_all_values() 
        df = pd.DataFrame(data[1:], columns=data[0])
        df = df.fillna(0)
        return df
    
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("GSheets 連線錯誤：找不到該試算表。請檢查 URL 是否正確。")
        return pd.DataFrame()
    except gspread.exceptions.WorksheetNotFound:
        # 如果找不到特定的表，顯示錯誤訊息並返回空 DataFrame
        st.error(f"GSheets 連線錯誤：找不到工作表 '{sheet_name}'。請檢查名稱是否正確。")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"⚠️ 讀取工作表 '{sheet_name}' 失敗。請檢查您的 Secrets 權限。")
        # st.exception(e) # 暫時註解掉，避免畫面過於混亂
        return pd.DataFrame() 

# --- 應用程式主體開始 ---

st.title("💰 投資組合儀表板")

# 【核心變更】：分別載入您需要的每一張表，並賦予不同的變數名稱
df_A = load_data("表A_持股總表")
df_B = load_data("表B_持股比例")
df_C = load_data("表C_總覽")
df_D = load_data("表D_現金流")
df_E = load_data("表E_已實現損益")
# 您可以根據需要加入更多：
# df_F = load_data("表F_每日淨值")
# df_G = load_data("表G_財富藍圖")


# --- 1. 總覽數據顯示 (使用 df_C) ---
st.header("1. 投資總覽")
if not df_C.empty:
    # 總覽表通常只有兩欄 (項目, 數值)，適合轉置或直接顯示
    st.dataframe(df_C, use_container_width=True, hide_index=True)
else:
    st.warning("總覽數據載入失敗。")

# --- 2. 持股總表與比例圖 (使用 df_A 和 df_B) ---
st.header("2. 持股分析")

# 顯示持股總表
if not df_A.empty:
    with st.expander("持股總表 (表A_持股總表)", expanded=False):
        st.dataframe(df_A, use_container_width=True)

# 顯示持股比例圖
if not df_B.empty and '市值（元）' in df_B.columns and '股票' in df_B.columns:
    try:
        # 繪製圓餅圖 (使用表B的數據)
        df_chart = df_B[pd.to_numeric(df_B['市值（元）'], errors='coerce') > 0]
        if not df_chart.empty:
            fig = px.pie(
                df_chart, 
                values='市值（元）', 
                names='股票', 
                title='📊 投資組合比例'
            )
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning("無法產生持股比例圖。")


# --- 3. 交易紀錄 (使用 df_D 和 df_E) ---
st.header("3. 交易與現金流紀錄")

col1, col2 = st.columns(2)

with col1:
    if not df_D.empty:
        with st.expander("現金流紀錄 (表D_現金流)", expanded=False):
            st.dataframe(df_D, use_container_width=True)
    else:
        st.warning("現金流數據載入失敗。")

with col2:
    if not df_E.empty:
        with st.expander("已實現損益 (表E_已實現損益)", expanded=False):
            st.dataframe(df_E, use_container_width=True)
    else:
        st.warning("已實現損益數據載入失敗。")


st.markdown("---")
st.info("🎯 **您的儀表板已成功讀取所有主要工作表！**")


