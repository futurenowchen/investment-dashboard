import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 設定網頁標題與佈局
st.set_page_config(page_title="我的投資儀表板", layout="wide")

# --- 資料讀取與處理 (使用數字索引，避開中文編碼問題) ---
@st.cache_data(ttl=60)
def load_google_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    try:
        # ==========================================
        # ⚠️ 這裡請依照你 Google Sheet 的實際順序修改數字
        # 0 代表最左邊第1張表，1 代表第2張...以此類推
        # ==========================================
        
        # 假設第1張表是「表A_持股總表」
        df_holdings = conn.read(worksheet=0) 
        
        # 假設第2張表是「表C_總覽」
        df_overview = conn.read(worksheet=2) 
        
        # 假設第3張表是「表D_現金流」
        df_cashflow = conn.read(worksheet=3)
        
        # 嘗試讀取表F (假設它是第4張表，如果不確定位置，請修改這個數字)
        try:
            df_table_f = conn.read(worksheet=5) 
        except:
            df_table_f = None
            
        return df_holdings, df_overview, df_cashflow, df_table_f
    except Exception as e:
        st.error(f"連線失敗！請確認 Google Sheet 的工作表順序是否正確。\n錯誤訊息: {e}")
        return None, None, None, None

# --- 通用資料清理函式 ---
def clean_numeric_columns(df, cols_to_clean=None):
    if df is None: return df
    if cols_to_clean is None: cols_to_clean = df.columns
    for col in cols_to_clean:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '', regex=False)\
                                         .str.replace('$', '', regex=False)\
                                         .str.replace('—', '', regex=False)\
                                         .str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

# 執行載入
with st.spinner('正在從雲端下載最新資料...'):
    df_holdings, df_overview, df_cashflow, df_table_f = load_google_data()

if df_holdings is None:
    st.stop()

# --- 資料清理邏輯 (針對中文欄位名稱) ---
# 1. 持股表
numeric_cols_holdings = ['持有數量（股）', '平均成本', '收盤價', '市值（元）', '浮動損益', '預估獲利率']
df_holdings = clean_numeric_columns(df_holdings, numeric_cols_holdings)
valid_holdings = df_holdings[df_holdings['股票'].notna() & (df_holdings['股票'] != '')].copy()

# 2. 現金流表
numeric_cols_cash = ['數量', '成交價', '淨收／支出', '累積現金']
df_cashflow = clean_numeric_columns(df_cashflow, numeric_cols_cash)
df_cashflow['日期'] = pd.to_datetime(df_cashflow['日期'], errors='coerce')

# 3. 總覽表
if df_overview.shape[1] >= 2:
    val_col_name = df_overview.columns[1] 
    df_overview = clean_numeric_columns(df_overview, [val_col_name])
    overview_dict = dict(zip(df_overview.iloc[:, 0], df_overview.iloc[:, 1]))
else:
    overview_dict = {}

# --- 頁面導航 ---
page = st.sidebar.radio("前往頁面", ["📊 資產總覽", "📈 持股分析", "💰 現金流向", "📑 表F 瀏覽"])

# --- 1. 資產總覽 ---
if page == "📊 資產總覽":
    st.title("📊 資產總覽 Dashboard")
    
    def get_val(key, default=0):
        return overview_dict.get(key, default) if pd.notnull(overview_dict.get(key)) else default

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("實質淨值 (NAV)", f"${get_val('實質NAV'):,.0f}", delta=f"槓桿: {get_val('槓桿倍數β', 1.0):.2f}x")
    col2.metric("總資產市值", f"${get_val('總資產市值'):,.0f}")
    col3.metric("現金部位", f"${get_val('現金'):,.0f}")
    col4.metric("借款餘額", f"${get_val('借款餘額'):,.0f}", delta_color="inverse")

    st.markdown("---")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("🎯 200萬目標達成進度")
        prog = min(max(float(get_val('達成進度', 0)), 0.0), 1.0)
        st.progress(prog)
        st.caption(f"目前進度: {prog*100:.1f}%")
    with c2:
        st.subheader("⚠️ 風險狀態")
        lev = get_val('槓桿倍數β', 1.0)
        status = "安全" if lev < 1.2 else "注意"
        color = "green" if status == "安全" else "orange"
        st.markdown(f"<h2 style='color:{color}; text-align:center; border:2px solid {color}; border-radius:10px;'>{status}</h2>", unsafe_allow_html=True)

# --- 2. 持股分析 ---
elif page == "📈 持股分析":
    st.title("📈 持股庫存分析")
    st.dataframe(valid_holdings.style.format({
        '市值（元）': '{:,.0f}', '浮動損益': '{:,.0f}', '預估獲利率': '{:.2%}'
    }), use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("持股比重")
        pie_data = valid_holdings[valid_holdings['市值（元）'] > 0]
        st.plotly_chart(px.pie(pie_data, values='市值（元）', names='股票', hole=0.4), use_container_width=True)
    with col2:
        st.subheader("浮動損益")
        valid_holdings['c'] = valid_holdings['浮動損益'].apply(lambda x: 'red' if x > 0 else 'green')
        st.plotly_chart(go.Figure(go.Bar(x=valid_holdings['股票'], y=valid_holdings['浮動損益'], marker_color=valid_holdings['c'])), use_container_width=True)

# --- 3. 現金流向 ---
elif page == "💰 現金流向":
    st.title("💰 現金流與交易紀錄")
    
    # 確保日期非空值再排序
    df_cashflow = df_cashflow.dropna(subset=['日期']).sort_values(by='日期', ascending=False)
    
    act = st.sidebar.multiselect("動作", df_cashflow['動作'].dropna().unique())
    stk = st.sidebar.multiselect("標的", df_cashflow['用途／股票'].dropna().unique())
    
    filt = df_cashflow.copy()
    if act: filt = filt[filt['動作'].isin(act)]
    if stk: filt = filt[filt['用途／股票'].isin(stk)]
    
    st.subheader("資金水位")
    chart = filt.dropna(subset=['累積現金']).sort_values('日期')
    if not chart.empty: st.plotly_chart(px.line(chart, x='日期', y='累積現金'), use_container_width=True)

    st.subheader("交易明細")
    cols = ['日期', '用途／股票', '動作', '數量', '成交價', '淨收／支出', '累積現金', '備註']
    st.dataframe(filt[[c for c in cols if c in filt.columns]].style.format({
        '淨收／支出': lambda x: f"{x:,.0f}" if pd.notnull(x) else "-",
        '累積現金': lambda x: f"{x:,.0f}" if pd.notnull(x) else "-",
        '日期': lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else ""
    }), use_container_width=True)

# --- 4. 表F 瀏覽 ---
elif page == "📑 表F 瀏覽":
    st.title("📑 表F 詳細資料")
    if df_table_f is not None:
        st.dataframe(df_table_f, use_container_width=True)
    else:
        st.warning("⚠️ 讀取不到第4張表 (Index=3)，請檢查 Google Sheet 的分頁數量。")