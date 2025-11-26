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

# 注入 CSS
st.markdown("""
<style>
html, body, [class*="stApp"] { font-size: 16px; }
h1 { font-size: 2.5em; } 
h2 { font-size: 1.8em; } 
h3 { font-size: 1.5em; } 
.stDataFrame { font-size: 1.0em; } 
.stMetric > div:first-child { font-size: 1.25em !important; }
.stMetric > div:nth-child(2) > div:first-child { font-size: 2.5em !important; }

div[data-testid="stSidebar"] .stButton button {
    width: 100%; height: 45px; margin-bottom: 10px; border: 1px solid #ccc;
}
div[data-testid="stMultiSelect"] > label { display: none; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JBI1pKWv9aw8dGCj89y9yNgoWG4YKllSMnPLpU_CCM/edit" 
# ==============================================================================

if 'live_prices' not in st.session_state:
    st.session_state['live_prices'] = {} 

# --- 核心工具函式：安全數值轉換 ---
def safe_float(value):
    """將各種髒亂的資料轉為浮點數 (計算用)"""
    if pd.isna(value) or value == '' or value is None: return 0.0
    try:
        s = str(value).strip()
        s = s.replace(',', '').replace('$', '').replace('¥', '').replace('%', '')
        s = s.replace('萬', '0000').replace('(', '-').replace(')', '')
        return float(s)
    except: return 0.0

# --- 顯示格式化函式 (轉為字串) ---
def fmt_money(value):
    """轉為 '1,234.56'"""
    val = safe_float(value)
    return f"{val:,.2f}" if val != 0 else "0.00"

def fmt_int(value):
    """轉為 '1,234'"""
    val = safe_float(value)
    return f"{val:,.0f}" if val != 0 else "0"

def fmt_date(value):
    """轉為 'YYYY-MM-DD'"""
    try:
        return pd.to_datetime(value).strftime('%Y-%m-%d')
    except:
        return str(value)

# 連線工具
def get_gsheet_connection():
    try:
        if "gsheets" not in st.secrets.get("connections", {}):
            st.error("Secrets 錯誤")
            return None, None
        if SHEET_URL == "YOUR_SPREADSHEET_URL_HERE":
            st.error("❌ 請先設定 SHEET_URL")
            return None, None
        
        secrets = dict(st.secrets["connections"]["gsheets"])
        secrets["private_key"] = secrets["private_key"].replace('\\n', '\n')
        gc = gspread.service_account_from_dict(secrets)
        return gc, gc.open_by_url(SHEET_URL)
    except Exception as e:
        st.error(f"連線錯誤: {e}")
        return None, None

# 數據載入 (純搬運，不做任何轉換)
@st.cache_data(ttl=None) 
def load_data(sheet_name): 
    with st.spinner(f"讀取: {sheet_name}"):
        try:
            _, sh = get_gsheet_connection()
            if not sh: return pd.DataFrame()
            
            ws = sh.worksheet(sheet_name) 
            data = ws.get_all_values()
            if not data: return pd.DataFrame()
            
            df = pd.DataFrame(data[1:], columns=data[0])
            # 處理重複欄位名
            if len(df.columns) != len(set(df.columns)):
                cols = []
                count = {}
                for c in df.columns:
                    n = "Unnamed" if not c else c
                    if n in count: count[n]+=1; cols.append(f"{n}_{count[n]}")
                    else: count[n]=0; cols.append(n)
                df.columns = cols
            return df
        except gspread.exceptions.WorksheetNotFound:
            return pd.DataFrame()
        except Exception as e:
            st.error(f"讀取失敗: {e}")
            return pd.DataFrame() 

# 股價 API
@st.cache_data(ttl="60s") 
def fetch_current_prices(tickers):
    st.info(f"更新 {len(tickers)} 支股票價格...")
    res = {}
    time.sleep(1)
    try:
        data = yf.download(tickers, period='1d', interval='1d', progress=False)
        if data.empty: return {}
        
        if len(tickers) == 1:
            val = data['Close'].iloc[-1]
            if hasattr(val, 'item'): val = val.item()
            res[tickers[0]] = round(val, 2)
        else:
            closes = data['Close'].iloc[-1]
            for t in tickers:
                val = closes.get(t)
                if pd.notna(val): res[t] = round(val, 2)
        return res
    except: return {}

# 寫入 API
def write_prices_to_sheet(df_A, updates):
    _, sh = get_gsheet_connection()
    if not sh: return False
    try:
        ws = sh.worksheet('表A_持股總表')
        vals = []
        for _, row in df_A.iterrows():
            t = str(row.get('股票','')).strip()
            p = updates.get(t)
            vals.append([f"{p}"]) if p else vals.append([''])
        
        ws.update(f'E2:E{2+len(vals)-1}', vals, value_input_option='USER_ENTERED')
        return True
    except: return False

# === 主程式 ===
st.title('💰 投資組合儀表板')

df_A = load_data('表A_持股總表')
df_B = load_data('表B_持股比例')
df_C = load_data('表C_總覽')
df_D = load_data('表D_現金流')
df_E = load_data('表E_已實現損益')
df_F = load_data('表F_每日淨值')
df_G = load_data('表G_財富藍圖') 

# 側邊欄
st.sidebar.header("🎯 數據管理")
if st.sidebar.button("🔄 重新載入資料"):
    load_data.clear()
    st.rerun()

if st.sidebar.button("💾 更新股價至 Google Sheets", type="primary"):
    if not df_A.empty and '股票' in df_A.columns:
        tickers = [t for t in df_A['股票'].unique() if t]
        updates = fetch_current_prices(tickers)
        st.session_state['live_prices'] = updates
        if updates and write_prices_to_sheet(df_A, updates):
            st.sidebar.success("更新成功")
            load_data.clear()
            st.rerun()
st.sidebar.markdown("---")

# 1. 總覽
st.header('1. 投資總覽')
if not df_C.empty:
    df_c = df_C.copy()
    df_c.set_index(df_c.columns[0], inplace=True)
    col_val = df_c.columns[0]
    
    risk = str(df_c.loc['β風險燈號', col_val]) if 'β風險燈號' in df_c.index else '未知'
    risk_txt = re.sub(r'\s+', '', risk)
    lev = safe_float(df_c.loc['槓桿倍數β', col_val]) if '槓桿倍數β' in df_c.index else 0

    # 燈號樣式
    style = {'e':'❓', 'bg':'#6c757d', 't':'white'}
    if '安全' in risk_txt: style = {'e':'✅', 'bg':'#28a745', 't':'white'} # 綠
    elif '警戒' in risk_txt: style = {'e':'⚠️', 'bg':'#ffc107', 't':'black'} # 黃
    elif '危險' in risk_txt: style = {'e':'🚨', 'bg':'#dc3545', 't':'white'} # 紅

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader('核心資產')
        mask = ~df_c.index.isin(['β風險燈號', '槓桿倍數β', '短期財務目標', '短期財務目標差距', '達成進度'])
        st.dataframe(df_c[mask], use_container_width=True)
    
    with c2:
        st.subheader('風險指標')
        st.markdown(f"<div style='background:{style['bg']};color:{style['t']};padding:15px;border-radius:10px;text-align:center;font-size:1.5em;font-weight:bold'>{style['e']} {risk}</div>", unsafe_allow_html=True)
        st.metric("槓桿倍數", f"{lev:.2f}")
        
        st.markdown("---")
        # 財務目標視覺強化
        try:
            target = safe_float(df_c.loc['短期財務目標', col_val]) if '短期財務目標' in df_c.index else 0
            gap = safe_float(df_c.loc['短期財務目標差距', col_val]) if '短期財務目標差距' in df_c.index else 0
            
            if target > 0:
                curr = target - gap
                pct = max(0.0, min(1.0, curr/target))
                
                st.markdown(f"""
                <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; margin-bottom:10px;">
                    <div style="font-size:1.1em; color:gray; margin-bottom:5px;">短期財務目標達成率</div>
                    <div style="font-size:2.5em; font-weight:bold; color:#007bff; line-height:1.2;">
                        {pct*100:.1f}%
                    </div>
                    <div style="margin-top:5px; font-size:0.9em; display:flex; justify-content:space-between;">
                        <span>目前: <b>${fmt_int(curr)}</b></span>
                        <span>目標: <b>${fmt_int(target)}</b></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(pct)
            else:
                st.caption("無法計算進度")
        except: pass

# 2. 持股
st.header('2. 持股分析')
c1, c2 = st.columns([1, 1])
with c1:
    if not df_A.empty:
        df_show = df_A.copy()
        if st.session_state['live_prices']:
            df_show['即時價'] = df_show['股票'].map(st.session_state['live_prices']).fillna('')
        
        for c in ['持有數量（股）', '市值（元）', '浮動損益']: 
            if c in df_show.columns: df_show[c] = df_show[c].apply(fmt_str_int)
        for c in ['平均成本', '收盤價', '即時價']:
            if c in df_show.columns: df_show[c] = df_show[c].apply(fmt_str_money)
            
        with st.expander("持股明細", expanded=True):
            st.dataframe(df_show, use_container_width=True)

with c2:
    if not df_B.empty and '市值（元）' in df_B.columns:
        df_B['num'] = df_B['市值（元）'].apply(safe_float)
        chart_data = df_B[(df_B['num'] > 0) & (~df_B['股票'].str.contains('總資產|Total', na=False))]
        if not chart_data.empty:
            st.plotly_chart(px.pie(chart_data, values='num', names='股票', title='資產配置'), use_container_width=True)

# 3. 交易紀錄
st.header('3. 交易紀錄與淨值')
t1, t2, t3 = st.tabs(['現金流', '已實現損益', '每日淨值'])

with t1:
    if not df_D.empty:
        df_calc = df_D.copy()
        if '日期' in df_calc.columns:
            df_calc['dt'] = pd.to_datetime(df_calc['日期'], errors='coerce')
            df_calc.sort_values('dt', ascending=False, inplace=True)
        
        cats = df_calc['動作'].unique().tolist()
        sel = st.multiselect('篩選動作', cats, default=cats)
        df_calc = df_calc[df_calc['動作'].isin(sel)]
        
        total = df_calc['淨收／支出'].apply(safe_float).sum() if '淨收／支出' in df_calc.columns else 0
        c_a, c_b = st.columns(2)
        c_a.metric("篩選淨額", fmt_str_money(total))
        c_b.markdown(f"**筆數：** {len(df_calc)}")
        
        df_view = df_calc.drop(columns=['dt'], errors='ignore').copy()
        if '日期' in df_view.columns: df_view['日期'] = df_view['日期'].apply(fmt_str_date)
        for c in ['淨收／支出', '累積現金', '成交價']:
            if c in df_view.columns: df_view[c] = df_view[c].apply(fmt_str_money)
        if '數量' in df_view.columns: df_view['數量'] = df_view['數量'].apply(fmt_str_int)
        
        st.dataframe(df_view, use_container_width=True, height=400)
        if not df_calc.empty:
            st.caption(f"📅 {df_calc['dt'].min().date()} ~ {df_calc['dt'].max().date()}")

with t2:
    if not df_E.empty:
        df_calc = df_E.copy()
        d_col = next((c for c in df_calc.columns if '日期' in c), None)
        if d_col:
            df_calc['dt'] = pd.to_datetime(df_calc[d_col], errors='coerce')
            df_calc.sort_values('dt', ascending=False, inplace=True)
        
        stocks = df_calc['股票'].unique().tolist()
        c_sel, c_all, c_clr = st.columns([4, 1, 1])
        with c_sel: sel_s = st.multiselect('篩選股票', stocks, default=stocks, key='pnl_s', label_visibility="collapsed")
        with c_all:
            st.markdown('<div style="height: 28px"></div>', unsafe_allow_html=True)
            if st.button("全選"): del st.session_state['pnl_s']; st.rerun()
        with c_clr:
            st.markdown('<div style="height: 28px"></div>', unsafe_allow_html=True)
            if st.button("清除"): st.session_state['pnl_s'] = []; st.rerun()
        
        if sel_s: df_calc = df_calc[df_calc['股票'].isin(sel_s)]
        
        total = df_calc['已實現損益'].apply(safe_float).sum() if '已實現損益' in df_calc.columns else 0
        st.metric("總實現損益", fmt_str_money(total))
        
        df_view = df_calc.drop(columns=['dt'], errors='ignore').copy()
        if d_col: df_view[d_col] = df_view[d_col].apply(fmt_str_date)
        for c in ['已實現損益', '投資成本', '帳面收入', '成交均價']:
             if c in df_view.columns: df_view[c] = df_view[c].apply(fmt_str_money)
             
        st.dataframe(df_view, use_container_width=True, height=400)

with t3:
    if not df_F.empty:
        df_calc = df_F.copy()
        if '實質NAV' in df_calc.columns and '日期' in df_calc.columns:
            df_calc['dt'] = pd.to_datetime(df_calc['日期'], errors='coerce')
            df_calc['nav'] = df_calc['實質NAV'].apply(safe_float)
            df_calc = df_calc.sort_values('dt') # 圖表依時間正序
            
            # 🎯 優化折線圖顯示：增加自定義 hovertemplate
            fig = px.line(
                df_calc, 
                x='dt', 
                y='nav', 
                title='📈 實質淨資產價值 (NAV) 走勢',
                labels={'dt': '日期', 'nav': '實質淨值'},
                markers=True # 增加數據點
            )
            # 自定義懸停提示 (Hover Tooltip)
            fig.update_traces(
                line_color='#007bff',
                hovertemplate="<b>日期:</b> %{x|%Y-%m-%d}<br><b>淨值:</b> %{y:,.0f}<extra></extra>"
            )
            fig.update_layout(
                hovermode="x unified", # 統一顯示X軸資訊
                yaxis_tickformat=",.0f" # Y軸千分位
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("詳細數據"):
                # 表格依時間倒序 (最新的在上面)
                df_disp = df_calc.sort_values('dt', ascending=False).drop(columns=['dt', 'nav']).copy()
                df_disp['日期'] = df_disp['日期'].apply(fmt_str_date)
                for c in ['實質NAV', '股票市值', '現金']:
                    if c in df_disp.columns: df_disp[c] = df_disp[c].apply(fmt_str_money)
                st.dataframe(df_disp, use_container_width=True)
                if not df_calc.empty:
                    st.caption(f"📅 紀錄範圍: {df_calc['dt'].min().date()} ~ {df_calc['dt'].max().date()} (共 {len(df_calc)} 筆)")

st.markdown('---')
# 4. 財富藍圖
st.header('4. 財富藍圖')
if not df_G.empty:
    try:
        for i, row in df_G.iterrows():
            level = row.get('階層') or row.iloc[0]
            money = row.get('美金金額範圍') or row.iloc[1]
            twd = row.get('約當台幣') or row.iloc[2]
            desc = row.get('財富階層意義') or row.iloc[3]
            time_est = row.get('以年報酬率18–20%推估所需時間') or (row.iloc[4] if len(row)>4 else "")
            
            with st.container():
                st.markdown(f"#### {level}")
                c1, c2, c3 = st.columns([2, 2, 3])
                c1.caption("資金範圍 (USD)")
                c1.write(f"**{money}**")
                c2.caption("約當台幣 (TWD)")
                c2.write(f"**{twd}**")
                c3.caption("階段意義")
                c3.info(desc)
                if time_est: st.success(f"🚀 推估時間: {time_est}")
                st.divider()
    except:
        st.dataframe(df_G, use_container_width=True)
else:
    st.info("無財富藍圖資料")
