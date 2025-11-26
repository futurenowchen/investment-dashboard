import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import yfinance as yf 
import gspread 
import time 
import re 
import numpy as np 

# 設置頁面配置
st.set_page_config(layout="wide", page_title="投資組合儀表板")

# 注入 CSS (修正按鈕樣式與字體)
st.markdown("""
<style>
html, body, [class*="stApp"] { font-size: 16px; }
h1 { font-size: 2.5em; } 
h2 { font-size: 1.8em; } 
h3 { font-size: 1.5em; } 
.stDataFrame { font-size: 1.0em; } 
.stMetric > div:first-child { font-size: 1.25em !important; }
.stMetric > div:nth-child(2) > div:first-child { font-size: 2.5em !important; }

/* 側邊欄按鈕樣式優化 */
div[data-testid="stSidebar"] .stButton button {
    width: 100%;
    height: 45px; 
    margin-bottom: 10px;
    border: 1px solid #ccc;
}

/* 隱藏 Multiselect 的標籤 */
div[data-testid="stMultiSelect"] > label { display: none; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 
# ==============================================================================

# 初始化 Session State
if 'live_prices' not in st.session_state:
    st.session_state['live_prices'] = {} 

# --- 核心工具函式：單一數值轉換 ---
def safe_float(value):
    """將單一字串轉換為浮點數，處理千分位、貨幣符號等。失敗返回 0.0"""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    try:
        # 移除常見非數字字符
        s = str(value).strip()
        s = s.replace(',', '').replace('$', '').replace('¥', '').replace('%', '')
        s = s.replace('萬', '0000') # 簡易處理萬
        s = s.replace('(', '-').replace(')', '')
        return float(s)
    except Exception:
        return 0.0

def fmt_str_currency(val):
    """將數值轉為格式化的字串 '1,234.00' (顯示用)"""
    f = safe_float(val)
    return f"{f:,.2f}"

def fmt_str_int(val):
    """將數值轉為格式化的整數字串 '1,234' (顯示用)"""
    f = safe_float(val)
    return f"{f:,.0f}"

# 連線工具函式
def get_gsheet_connection():
    try:
        if "gsheets" not in st.secrets.get("connections", {}):
            st.error("Secrets 錯誤：找不到 [connections.gsheets] 區塊。")
            return None, None
        if SHEET_URL == "YOUR_SPREADSHEET_URL_HERE":
            st.error("❌ 程式碼錯誤：請先將 SHEET_URL 替換為您的 Google Sheets 完整網址！")
            return None, None
        secrets_config = st.secrets["connections"]["gsheets"]
        # 處理 private_key 換行問題
        credentials_info = dict(secrets_config)
        if "\\n" in credentials_info["private_key"]:
            credentials_info["private_key"] = credentials_info["private_key"].replace('\\n', '\n')
        
        gc = gspread.service_account_from_dict(credentials_info)
        spreadsheet = gc.open_by_url(SHEET_URL)
        return gc, spreadsheet
    except Exception as e:
        st.error(f"⚠️ 連線錯誤: {e}")
        return None, None

# 數據載入函式 (原始載入，不做任何清理，保證不崩潰)
@st.cache_data(ttl=None) 
def load_data(sheet_name): 
    with st.spinner(f"讀取: {sheet_name}"):
        try:
            _, spreadsheet = get_gsheet_connection()
            if not spreadsheet: return pd.DataFrame()
            
            worksheet = spreadsheet.worksheet(sheet_name) 
            data = worksheet.get_all_values() 
            
            if not data: return pd.DataFrame()
            
            # 建立原始 DataFrame (全都是字串)
            df = pd.DataFrame(data[1:], columns=data[0])
            return df
        except gspread.exceptions.WorksheetNotFound:
            # 不報錯，只回傳空值，避免中斷其他表
            return pd.DataFrame()
        except Exception as e:
            st.error(f"讀取 '{sheet_name}' 失敗: {e}")
            return pd.DataFrame() 

# 獲取股價函式
@st.cache_data(ttl="60s") 
def fetch_current_prices(valid_tickers):
    st.info(f"獲取 {len(valid_tickers)} 支股票價格中...")
    price_updates = {}
    time.sleep(1) 
    try:
        data = yf.download(valid_tickers, period='1d', interval='1d', progress=False)
        if data.empty: return {}
        
        # 處理單支或多支股票
        if len(valid_tickers) == 1:
            latest = data['Close'].iloc[-1]
            # 檢查是否為單一數值
            if isinstance(latest, (int, float)) and not pd.isna(latest):
                price_updates[valid_tickers[0]] = round(latest, 2)
            elif isinstance(latest, pd.Series) and not latest.empty:
                 # yfinance 有時返回 Series
                 price_updates[valid_tickers[0]] = round(latest.item(), 2)
        else:
            latest_prices_df = data['Close'].iloc[-1]
            for ticker in valid_tickers:
                price = latest_prices_df.get(ticker)
                if price is not None and not pd.isna(price):
                    price_updates[ticker] = round(price, 2)
        return price_updates
    except Exception as e:
        st.error(f"股價獲取錯誤: {e}")
        return {}

# 寫入函式
def write_prices_to_sheet(df_A, price_updates):
    _, spreadsheet = get_gsheet_connection()
    if not spreadsheet: return False
    try:
        worksheet = spreadsheet.worksheet('表A_持股總表')
        write_values = []
        for index, row in df_A.iterrows():
            ticker = str(row.get('股票', '')).strip()
            price = price_updates.get(ticker) 
            write_values.append([f"{price}"]) if price is not None else write_values.append([''])
        
        # 假設 E 欄是最新收盤價 (從第2行開始寫)
        start_row = 2 
        end_row = start_row + len(write_values) - 1
        range_to_update = f'E{start_row}:E{end_row}'
        worksheet.update(range_to_update, write_values, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"寫入失敗: {e}")
        return False

# ======================== 應用程式主體 ========================

st.title('💰 投資組合儀表板')

# 1. 載入數據 (這裡只會拿到純文字 DataFrame，絕對安全)
df_A = load_data('表A_持股總表')
df_B = load_data('表B_持股比例')
df_C = load_data('表C_總覽')
df_D = load_data('表D_現金流')
df_E = load_data('表E_已實現損益')
df_F = load_data('表F_每日淨值')
df_G = load_data('表G_財富藍圖') 

# --- 側邊欄功能 ---
st.sidebar.header("🎯 數據管理")

if st.sidebar.button("🔄 重新載入所有數據"):
    load_data.clear()
    st.rerun()

if st.sidebar.button("💾 更新股價至 Google Sheets", type="primary"):
    if not df_A.empty and '股票' in df_A.columns:
        tickers = df_A['股票'].astype(str).str.strip().unique()
        valid_tickers = [t for t in tickers if t and t != 'nan']
        if valid_tickers:
            updates = fetch_current_prices(valid_tickers)
            st.session_state['live_prices'] = updates
            if updates and write_prices_to_sheet(df_A, updates):
                st.sidebar.success("更新成功！正在重新載入...")
                load_data.clear()
                st.rerun()
        else:
            st.sidebar.warning("未找到股票代碼")
    else:
        st.sidebar.error("表A 缺少 '股票' 欄位")
        
st.sidebar.markdown("---")

# --- 1. 投資總覽 ---
st.header('1. 投資總覽') 
if not df_C.empty:
    try:
        df_C_disp = df_C.copy()
        # 假設第一欄是項目，第二欄是數值
        df_C_disp.set_index(df_C_disp.columns[0], inplace=True)
        val_col = df_C_disp.columns[0] 
        
        # 安全提取數據
        risk_raw = str(df_C_disp.loc['β風險燈號', val_col]) if 'β風險燈號' in df_C_disp.index else '未知'
        risk_clean = re.sub(r'\s+', '', risk_raw)
        
        lev_raw = df_C_disp.loc['槓桿倍數β', val_col] if '槓桿倍數β' in df_C_disp.index else 0
        leverage = safe_float(lev_raw)

        # 風險燈號顏色定義
        colors = {
            '安全': {'emoji': '✅', 'bg': '#28a745', 'text': 'white'}, 
            '警戒': {'emoji': '⚠️', 'bg': '#ffc107', 'text': 'black'}, 
            '危險': {'emoji': '🚨', 'bg': '#dc3545', 'text': 'white'}
        }
        # 預設顏色
        style = {'emoji': '❓', 'bg': '#6c757d', 'text': 'white'}
        
        if '安全' in risk_clean: style = colors['安全']
        elif '警戒' in risk_clean: style = colors['警戒']
        elif '危險' in risk_clean: style = colors['危險']

        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader('核心資產')
            mask = ~df_C_disp.index.isin(['β風險燈號', '槓桿倍數β', '短期財務目標', '短期財務目標差距', '達成進度'])
            # 格式化數值，不使用 style
            df_table = df_C_disp[mask].copy()
            # 嘗試將表格內容格式化 (如果是數字)
            # 這裡簡單顯示原始值，避免過度處理
            st.dataframe(df_table, use_container_width=True)
        
        with c2:
            st.subheader('風險指標')
            st.markdown(f"<div style='background:{style['bg']};color:{style['text']};padding:15px;border-radius:10px;text-align:center;font-weight:bold;font-size:1.5em'>{style['emoji']} {risk_raw}</div>", unsafe_allow_html=True)
            st.metric("槓桿倍數 β", f"{leverage:.2f}")
            
            st.markdown("---")
            st.subheader('🎯 財富目標進度')
            
            t_val = safe_float(df_C_disp.loc['短期財務目標', val_col]) if '短期財務目標' in df_C_disp.index else 0
            gap_val = safe_float(df_C_disp.loc['短期財務目標差距', val_col]) if '短期財務目標差距' in df_C_disp.index else 0
            
            if t_val > 0:
                curr = t_val - gap_val
                pct = min(1.0, max(0.0, curr / t_val))
                pct_disp = pct * 100
                
                # 視覺強化：大字體顯示進度
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 5px;">
                    <span style="font-size: 1.1em; font-weight: bold;">短期目標</span>
                    <span style="font-size: 2.0em; font-weight: bold; color: #007bff;">{pct_disp:.1f}%</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.progress(pct)
                st.caption(f"目前: {curr:,.0f} / 目標: {t_val:,.0f} (差距: {gap_val:,.0f})")
            else:
                st.caption("無法計算進度 (目標需大於0)")
    except Exception as e:
        st.error(f"顯示總覽時發生錯誤: {e}")

# --- 2. 持股分析 ---
st.header('2. 持股分析')
c1, c2 = st.columns([1, 1])
with c1:
    if not df_A.empty:
        df_A_show = df_A.copy()
        
        # 即時價格
        if st.session_state['live_prices']:
            df_A_show['即時價'] = df_A_show['股票'].astype(str).str.strip().map(st.session_state['live_prices']).fillna('')

        # 格式化為字串 (安全做法)
        format_cols = ['持有數量（股）', '平均成本', '收盤價', '市值（元）', '浮動損益']
        for col in format_cols:
            if col in df_A_show.columns:
                df_A_show[col] = df_A_show[col].apply(fmt_str_currency if '成本' in col or '價' in col or '市值' in col or '損益' in col else fmt_str_int)
        
        with st.expander("持股明細", expanded=True):
            st.dataframe(df_A_show, use_container_width=True)

with c2:
    if not df_B.empty and '市值（元）' in df_B.columns:
        try:
            # 轉換數值用於繪圖 (僅此處轉換，不影響表格)
            df_B['市值_num'] = df_B['市值（元）'].apply(safe_float)
            # 排除總資產
            df_chart = df_B[~df_B['股票'].str.contains('總資產|Total', na=False)]
            df_chart = df_chart[df_chart['市值_num'] > 0]
            
            if not df_chart.empty:
                fig = px.pie(df_chart, values='市值_num', names='股票', title='投資組合比例')
                st.plotly_chart(fig, use_container_width=True)
        except Exception: pass

# --- 3. 交易紀錄 ---
st.header('3. 交易紀錄與淨值')
tab1, tab2, tab3 = st.tabs(['現金流', '已實現損益', '每日淨值'])

with tab1:
    if not df_D.empty:
        try:
            df_view = df_D.copy()
            # 排序處理 (先轉 datetime 排序，再轉回字串顯示)
            if '日期' in df_view.columns:
                df_view['_dt'] = pd.to_datetime(df_view['日期'], errors='coerce')
                df_view = df_view.sort_values('_dt', ascending=False)
                df_view['日期'] = df_view['_dt'].dt.strftime('%Y-%m-%d').fillna(df_view['日期'])
                df_view.drop(columns=['_dt'], inplace=True)

            # 篩選
            if '動作' in df_view.columns:
                cats = df_view['動作'].unique().tolist()
                sel_cats = st.multiselect('篩選動作', cats, default=cats, key='cf_filter')
                df_view = df_view[df_view['動作'].isin(sel_cats)]

            # 計算總額 (需轉數字)
            total = df_view['淨收／支出'].apply(safe_float).sum() if '淨收／支出' in df_view.columns else 0
            
            c_stat1, c_stat2 = st.columns(2)
            c_stat1.metric("💰 篩選總額", f"{total:,.0f}")
            c_stat2.markdown(f"**筆數：** {len(df_view)}")
            
            # 格式化表格 (轉字串)
            for col in ['淨收／支出', '累積現金', '成交價']:
                 if col in df_view.columns: df_view[col] = df_view[col].apply(fmt_str_currency)
            if '數量' in df_view.columns: df_view['數量'] = df_view['數量'].apply(fmt_str_int)
                
            st.dataframe(df_view, use_container_width=True, height=300)
            
            # 底部標註
            if not df_view.empty:
                d_min = df_view['日期'].min()
                d_max = df_view['日期'].max()
                st.caption(f"範圍: {d_min} ~ {d_max}")
        except Exception as e: st.error(f"顯示錯誤: {e}")
    else: st.warning("無數據")

with tab2:
    if not df_E.empty:
        try:
            df_view = df_E.copy()
            # 排序
            date_col = next((c for c in df_view.columns if '日期' in c), None)
            if date_col:
                df_view['_dt'] = pd.to_datetime(df_view[date_col], errors='coerce')
                df_view = df_view.sort_values('_dt', ascending=False)
                df_view[date_col] = df_view['_dt'].dt.strftime('%Y-%m-%d').fillna(df_view[date_col])
                df_view.drop(columns=['_dt'], inplace=True)

            # 篩選
            if '股票' in df_view.columns:
                stocks = df_view['股票'].unique().tolist()
                c_sel, c_btn1, c_btn2 = st.columns([4, 1, 1])
                with c_sel: 
                    sel_stocks = st.multiselect('篩選股票', stocks, default=stocks, key='pnl_sel', label_visibility="collapsed")
                    st.markdown("##### 篩選股票") # Label hack
                
                with c_btn1: 
                    # 透過 callback 或重整來處理全選 (這裡簡化處理)
                    if st.button('全選', key='btn_all'): 
                        st.session_state.pop('pnl_sel', None)
                        st.rerun()
                with c_btn2: 
                    if st.button('清除', key='btn_clear'):
                        # 無法直接清空 default 設為 all 的 multiselect，需配合 session state 邏輯
                        # 這裡做簡單重整示意
                        pass 
                
                if sel_stocks:
                    df_view = df_view[df_view['股票'].isin(sel_stocks)]

            total = df_view['已實現損益'].apply(safe_float).sum() if '已實現損益' in df_view.columns else 0
            st.metric("🎯 總實現報酬", f"{total:,.0f}")
            
            # 格式化
            fmt_cols = ['已實現損益', '投資成本', '帳面收入', '成交均價']
            for col in fmt_cols:
                if col in df_view.columns: df_view[col] = df_view[col].apply(fmt_str_currency)
            
            st.dataframe(df_view, use_container_width=True, height=300)
        except Exception as e: st.error(f"顯示錯誤: {e}")

with tab3:
    if not df_F.empty:
        try:
            df_view = df_F.copy()
            if '日期' in df_view.columns and '實質NAV' in df_view.columns:
                # 繪圖數據 (需數字)
                df_chart = df_view.copy()
                df_chart['dt'] = pd.to_datetime(df_chart['日期'], errors='coerce')
                df_chart['nav'] = df_chart['實質NAV'].apply(safe_float)
                df_chart = df_chart.sort_values('dt')
                
                fig = px.line(df_chart, x='dt', y='nav', title='NAV 趨勢')
                st.plotly_chart(fig, use_container_width=True)
                
                # 表格數據 (轉字串)
                with st.expander("詳細數據"):
                    df_disp = df_view.copy()
                    df_disp['_dt'] = pd.to_datetime(df_disp['日期'], errors='coerce')
                    df_disp = df_disp.sort_values('_dt', ascending=False)
                    df_disp['日期'] = df_disp['_dt'].dt.strftime('%Y-%m-%d')
                    df_disp.drop(columns=['_dt'], inplace=True)
                    
                    for c in ['實質NAV', '股票市值', '現金']:
                        if c in df_disp.columns: df_disp[c] = df_disp[c].apply(fmt_str_currency)
                    
                    st.dataframe(df_disp, use_container_width=True)
        except Exception: st.warning("每日淨值顯示異常")

st.markdown('---')
# 4. 財富藍圖 (文章式呈現)
st.header('4. 財富藍圖')
if not df_G.empty:
    # 假設有欄位: '階層', '美金金額範圍', '財富階層意義'
    # 我們用迭代的方式顯示為卡片，而非表格
    try:
        for index, row in df_G.iterrows():
            # 簡單的卡片樣式
            with st.container():
                c1, c2 = st.columns([1, 3])
                with c1:
                    st.markdown(f"### {row.get('階層', '')}")
                    st.caption(row.get('美金金額範圍', ''))
                with c2:
                    st.markdown(f"**{row.get('約當台幣', '')}**")
                    st.write(row.get('財富階層意義', ''))
                    if '以年報酬率18–20%推估所需時間' in row:
                        st.info(f"⏳ {row['以年報酬率18–20%推估所需時間']}")
                st.divider()
    except Exception:
        # 如果格式不對，退回顯示表格
        st.dataframe(df_G, use_container_width=True)
else:
    st.info("無財富藍圖資料")
