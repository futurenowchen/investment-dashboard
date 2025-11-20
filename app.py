import streamlit as st
import pandas as pd
import plotly.express as px
import gspread 
from datetime import datetime
import yfinance as yf # 🎯 新增：用於獲取股票價格

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
            
            # 🎯 修正重複欄位名稱
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
            st.error(f'GSheets 連線失敗：找不到試算表。請檢查 SHEET_URL 是否正確。')
            return pd.DataFrame()
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"GSheets 連線失敗：找不到工作表 '{sheet_name}'。請檢查名稱是否完全正確。")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"⚠️ 讀取工作表 '{sheet_name}' 發生未知錯誤。")
            st.exception(e) 
            return pd.DataFrame() 


# 新增的函式：用於獲取工作表連線，專門用於寫入操作
def get_worksheet_connection(sheet_name):
    """建立 gspread 連線並返回指定的工作表物件，用於寫入資料。"""
    try:
        secrets_config = st.secrets["connections"]["gsheets"]
        credentials_info = dict(secrets_config) 
        credentials_info["private_key"] = credentials_info["private_key"].replace('\\n', '\n')
        
        gc = gspread.service_account_from_dict(credentials_info)
        spreadsheet = gc.open_by_url(SHEET_URL)
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet
    except Exception as e:
        st.error(f"連線到工作表 '{sheet_name}' 進行寫入操作時發生錯誤。請確保服務帳戶有編輯權限。")
        st.exception(e)
        return None

# 🎯 核心新功能：自動更新股價並寫回 Google Sheet (約 125 行)
def update_stock_prices(df_A):
    """從 yfinance 獲取最新收盤價並寫入 '表A_持股總表'。"""
    
    # 確保 '股票' 欄位存在，且不是空的 DataFrame
    if df_A.empty or '股票' not in df_A.columns:
        st.error("❌ '表A_持股總表' 數據不完整，請確保包含 '股票' 代碼欄位。")
        return

    # 獲取所有唯一的股票代碼，並過濾掉空值
    tickers = df_A['股票'].astype(str).str.strip().unique()
    valid_tickers = [t for t in tickers if t]
    
    if not valid_tickers:
        st.warning("工作表中沒有找到有效的股票代碼 (e.g., 2330.TW, AAPL)。")
        return

    st.info(f"正在獲取 {len(valid_tickers)} 支股票的最新收盤價...")
    
    price_updates = {}
    
    # 使用 yfinance 獲取數據
    try:
        # 獲取最新價格 (period='1d' 效率最高)
        data = yf.download(valid_tickers, period='1d', interval='1d', progress=False)

        if data.empty:
            st.warning("無法從 yfinance 獲取任何數據，請檢查網絡或代碼是否正確。")
            return
        
        # 處理單一支股票和多支股票的返回格式
        if len(valid_tickers) == 1:
            # 單一股票返回 Series，需要轉換成 DataFrame 格式
            latest_prices = data['Close'].iloc[-1] 
            # 由於是單一股票，直接使用 ticker 作為鍵
            if not pd.isna(latest_prices):
                price_updates[valid_tickers[0]] = latest_prices
        else:
            # 多支股票返回 DataFrame
            latest_prices_df = data['Close'].iloc[-1]
            for ticker in valid_tickers:
                price = latest_prices_df.get(ticker)
                if price is not None and not pd.isna(price):
                    price_updates[ticker] = price
        
    except Exception as e:
        st.error(f"❌ 獲取股價時發生錯誤：{e}")
        return

    if not price_updates:
        st.warning("沒有成功獲取到任何股票的最新價格。")
        return

    # 寫回 Google Sheets
    try:
        worksheet = get_worksheet_connection('表A_持股總表')
        if not worksheet: return

        # 獲取整個工作表的數據 (包含標頭)
        all_data = worksheet.get_all_values()
        headers = all_data[0]
        data_rows = all_data[1:]
        
        # 🎯 DEBUG: 在側邊欄顯示實際讀到的欄位名稱，供用戶診斷
        st.sidebar.info(f"表A讀取到的欄位名稱：{headers}") 
        
        # 找到 '股票' 和 '最新收盤價' 的欄位索引
        try:
            # 🎯 修正: 先清理欄位名稱的頭尾空白後再進行索引查找，提高容錯性
            cleaned_headers = [h.strip() for h in headers]
            ticker_col_idx = cleaned_headers.index('股票')
            price_col_idx = cleaned_headers.index('最新收盤價')
        except ValueError:
            st.error("❌ 寫入失敗：工作表 '表A_持股總表' 必須包含【完全匹配】的欄位：'股票' 和 '最新收盤價'。")
            st.code(f"您的欄位名稱: {headers}")
            return

        # 準備更新的範圍和值
        updates = []
        for i, row in enumerate(data_rows):
            # i+2 是實際的行號 (標頭佔用第 1 行)
            row_num = i + 2 
            
            # 確保行長度足夠
            if len(row) > ticker_col_idx:
                ticker = row[ticker_col_idx].strip()
                
                if ticker in price_updates:
                    new_price = round(price_updates[ticker], 4)
                    
                    # 檢查該行是否足夠長來容納新價格，如果不足，則填充空字串
                    if len(row) <= price_col_idx:
                        row.extend([''] * (price_col_idx - len(row) + 1))
                    
                    # 檢查舊價格是否需要更新
                    if str(row[price_col_idx]) != str(new_price):
                        # 創建更新範圍 (e.g., 'C2', 'C3'...)
                        cell_range = gspread.utils.rowcol_to_a1(row_num, price_col_idx + 1)
                        updates.append({
                            'range': cell_range,
                            'values': [[str(new_price)]]
                        })

        if updates:
            # 批量更新，效率最高
            worksheet.batch_update(updates, value_input_option='USER_ENTERED')
            st.success(f"🎉 成功更新 {len(updates)} 筆最新收盤價！")
            
            # 清除快取，讓 Streamlit 重新載入數據
            st.cache_data.clear()
        else:
            st.info("所有股票價格已是最新，無需更新。")

    except Exception as e:
        st.error(f"❌ 寫入 Google Sheets 失敗：{e}")
        st.exception(e)


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
# 0. 股價即時更新區塊 (新增，位於側邊欄)
# ---------------------------------------------------
st.sidebar.header("🎯 股價數據管理")
if st.sidebar.button("🔄 更新最新收盤價 (寫入 Sheets)", type="primary"):
    with st.spinner('正在從 yfinance 獲取數據並寫回 Google Sheets...'):
        # 🎯 這裡會執行更新，並在失敗時顯示診斷資訊
        update_stock_prices(df_A)
        # 刷新頁面，確保重新讀取數據
        st.rerun() 
st.sidebar.caption("💡 點擊後會覆蓋 '表A_持股總表' 中的 '最新收盤價' 欄位。")
st.sidebar.markdown("---")

# ---------------------------------------------------
# 1. 投資總覽 (核心總覽表格 + 風險指標燈號)
# ---------------------------------------------------
st.header('1. 投資總覽') 
if not df_C.empty:
    
    df_C_display = df_C.copy()
    
    # 🎯 欄位處理：確保索引設置和欄位名稱唯一性 (解決 ValueError)
    df_C_display.set_index(df_C_display.columns[0], inplace=True)
    
    # 2. 將剩下的唯一一欄（數值）重新命名為 '數值'
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
# 4. 資料輸入與管理 (新增現金流)
# ---------------------------------------------------
st.header('4. 資料輸入與管理')

# 使用 Tab 來分開不同的輸入類型
tab_cash, tab_blueprint = st.tabs(['新增現金流交易 (表D)', '財富藍圖 (表G)'])

with tab_cash:
    st.subheader('新增現金流交易')
    st.warning('⚠️ 注意：此功能會直接在您的 Google Sheets "表D_現金流" 最後新增一行資料。')

    # 建立 Streamlit 表單
    with st.form("cash_flow_form", clear_on_submit=True):
        
        # 獲取今日日期作為預設值
        default_date = datetime.now().date()
        date = st.date_input("日期", default_date)
        
        item = st.selectbox(
            "項目 (請與您的表格欄位相符)",
            ['投入資金', '贖回資金', '股息/利息收入', '費用/稅金', '其他'],
            index=0
        )
        
        # 確保金額是正數輸入，程式內部再處理正負號
        amount = st.number_input("金額 (例如：投入/流入 輸入 10000)", min_value=0.0, format="%.2f")
        
        is_outflow = st.checkbox("這是流出/贖回交易 (勾選表示金額為負數)")
        
        submitted = st.form_submit_button("✅ 送出交易")

        if submitted:
            if SHEET_URL == "YOUR_SPREADSHEET_URL_HERE":
                st.error("請先在程式碼開頭替換 SHEET_URL！無法寫入。")
            elif amount == 0.0:
                st.error("金額不能為零。")
            else:
                try:
                    worksheet = get_worksheet_connection('表D_現金流')
                    if worksheet:
                        
                        final_amount = -amount if is_outflow else amount
                        
                        # 根據金額正負調整為流入或流出
                        inflow = final_amount if final_amount > 0 else 0
                        outflow = abs(final_amount) if final_amount < 0 else 0
                        
                        # 這裡假設您的 Google Sheet 欄位順序是: 日期 | 項目 | 流入金額 | 流出金額 | 備註
                        new_row = [
                            date.strftime('%Y/%m/%d'), 
                            item, 
                            inflow, 
                            outflow, 
                            "" # 備註欄 (請確保這個列表的長度與您的 Sheet 欄位數匹配)
                        ] 

                        worksheet.append_row(new_row, value_input_option='USER_ENTERED')
                        
                        # 成功後，清除快取，讓儀表板自動刷新數據
                        st.cache_data.clear()
                        st.success(f"成功新增一筆交易：{item}, 金額: {final_amount:.2f}")

                except Exception as e:
                    st.error(f"寫入 Google Sheets 失敗：{e}")
                    st.exception(e)


# ---------------------------------------------------
# 5. 財富藍圖
# ---------------------------------------------------
if not df_G.empty:
    with st.expander('5. 財富藍圖 (表G_財富藍圖)', expanded=False):
        st.dataframe(df_G, use_container_width=True)
