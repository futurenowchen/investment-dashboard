import streamlit as st
import pandas as pd
import plotly.express as px # 假設您後續會使用 Plotly 繪製圖表

# 設置頁面配置
st.set_page_config(layout="wide")

# ==============================================================================
# 請務必替換成您 Google Sheets 的【完整網址】
# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 
# 假設您的主要持股資料工作表名稱是這個
SHEET_NAME = "七表_GSheets線上維護版" 
# ==============================================================================


# 使用 Streamlit 內建的 gsheets 連線器，並加入數據快取
@st.cache_data(ttl="10m") # 設置快取時間為 10 分鐘，加快重複讀取速度
def load_data():
    if SHEET_URL == "YOUR_SPREADSHEET_URL_HERE":
        st.error("❌ 請先將代碼中的 SHEET_URL 替換為您的 Google Sheets 完整網址！")
        return pd.DataFrame()

    try:
        # 建立連線實例。
        # Streamlit 會自動使用您在 Secrets 中設定的 [connections.gsheets] 資訊。
        # 這是取代 'streamlit-gsheets' 的官方標準方法。
        conn = st.connection("gsheets", type="gsheets")
        
        # 讀取數據
        df = conn.read(
            spreadsheet=SHEET_URL,
            worksheet=SHEET_NAME,
            # 讀取所有欄位。如果您確定要讀前8欄，可以改為 usecols=list(range(8))
        )
        
        # 執行資料清理 (將 NaN 替換為 0，避免計算錯誤)
        df = df.fillna(0)
        return df
    
    except Exception as e:
        st.error(f"⚠️ 數據讀取失敗！請檢查 Google Sheets 網址、工作表名稱或 Secrets 權限。")
        st.exception(e) # 顯示詳細錯誤，方便您除錯
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
