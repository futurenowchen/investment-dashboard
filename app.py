import streamlit as st
import pandas as pd
import time
import re
from datetime import datetime
import data_manager as dm
import visuals as vis

# 設置頁面配置
st.set_page_config(layout="wide", page_title="投資組合儀表板")

# 注入 CSS (來自 visuals.py)
st.markdown(vis.get_custom_css(), unsafe_allow_html=True)

if 'live_prices' not in st.session_state:
    st.session_state['live_prices'] = {}

# === 主程式 ===

# 載入基礎資料 (供側邊欄與下方區塊使用)
df_A = dm.load_data('表A_持股總表')
df_B = dm.load_data('表B_持股比例')
df_C_base = dm.load_data('表C_總覽')
df_D = dm.load_data('表D_現金流')
df_E = dm.load_data('表E_已實現損益')
df_F = dm.load_data('表F_每日淨值')
df_G = dm.load_data('表G_財富藍圖') 
df_Monitor_base = dm.load_data('即時監控面板')
df_Market_base = dm.load_data('Market')

# 決定標題日期字串 (直接抓取系統今日時間)
today = datetime.now()
date_str = f" - {today.year}年{today.month}月{today.day}日"

st.title(f'💰 投資組合儀表板{date_str}')

# --- Sidebar ---
st.sidebar.header("🎯 數據管理")
if st.sidebar.button("🔄 重新載入全域資料"):
    dm.load_data.clear()
    st.rerun()

# 戰術升級：局部無感跳動開關
auto_refresh = st.sidebar.checkbox("⏱️ 啟動局部無感跳動 (每 60 秒)", value=False)
refresh_interval = 60 if auto_refresh else None
if auto_refresh:
    st.sidebar.info("🟢 戰術雷達：局部掃描啟動")

if st.sidebar.button("💾 更新股價至 Google Sheets", type="primary"):
    if not df_A.empty and '股票' in df_A.columns:
        tickers = [t for t in df_A['股票'].unique() if str(t).strip()]
        st.toast(f"正在更新 {len(tickers)} 檔股價...", icon="⏳")
        updates = dm.fetch_current_prices(tickers)
        st.session_state['live_prices'] = updates
        if updates:
            success = dm.write_prices_to_sheet(df_A, updates)
            if success:
                st.sidebar.success(f"成功更新 {len(updates)} 檔股價！")
                time.sleep(1)
                dm.load_data.clear()
                st.rerun()
        else:
            st.sidebar.warning("未能取得任何股價，請檢查代碼或網路。")

st.sidebar.markdown("---")
st.sidebar.subheader("📋 匯出功能")
if st.sidebar.button("產生文字日報"):
    report_text = dm.generate_daily_report(df_A, df_C_base, df_D, df_E, df_F, df_Monitor_base, st.session_state['live_prices'], df_Market_base)
    st.sidebar.markdown("請點擊下方代碼區塊右上角的 **複製按鈕**：")
    st.sidebar.code(report_text, language='text')

st.sidebar.markdown("---")
with st.sidebar.expander("🛠️ 連線狀態檢查"):
    st.write(f"目前設定的 Sheet URL: `{dm.SHEET_URL}`")
    if "connections" in st.secrets: st.success("✅ Secrets 設定已偵測到")
    else: st.error("❌ 找不到 Secrets 設定")
st.sidebar.markdown("---")


# ==========================================
# 🛡️ 戰略高頻監控區 (Fragment Protocol 局部重載)
# ==========================================
@st.fragment(run_every=refresh_interval)
def render_live_monitoring_fragment():
    # 每次局部重載時，讀取最新快取資料 (透過 TTL 60 秒機制確保數據為最新)
    df_Monitor = dm.load_data('即時監控面板')
    df_C = dm.load_data('表C_總覽')
    df_Market = dm.load_data('Market')

    st.header('1. 投資總覽')

    # 準備總覽卡片數據
    tot_asset_str = "0"
    cash_str = "0"
    nav_nc_str = "0"
    nav_vol_str = "0%"
    nav_nc_color = "#212529"

    stock_value_str = "0"
    stock_nc_str = "0"
    stock_vol_str = "0%"
    stock_nc_color = "#212529"

    pct_float = 0.0
    lev_str = "0%"
    e_val = "0%"

    if not df_Monitor.empty:
        tot_asset_str = dm.fmt_int(df_Monitor['總資產'].iloc[0]) if '總資產' in df_Monitor.columns else "0"
        cash_str = dm.fmt_int(df_Monitor['現金'].iloc[0]) if '現金' in df_Monitor.columns else "0"
        stock_value_str = dm.fmt_int(df_Monitor['股票市值'].iloc[0]) if '股票市值' in df_Monitor.columns else "0"
        
        # NAV淨變動 / 波動率
        nnc_val = dm.safe_float(df_Monitor['NAV淨變動'].iloc[0]) if 'NAV淨變動' in df_Monitor.columns else 0
        nav_nc_str = f"+{dm.fmt_int(nnc_val)}" if nnc_val > 0 else dm.fmt_int(nnc_val)
        if nnc_val > 0: nav_nc_color = "#EF4444" 
        elif nnc_val < 0: nav_nc_color = "#10B981"
        
        nv_val = df_Monitor['NAV波動率'].iloc[0] if 'NAV波動率' in df_Monitor.columns else '0%'
        nav_vol_str = nv_val if isinstance(nv_val, str) and '%' in nv_val else dm.fmt_pct(nv_val)

        # 股市淨變動 / 波動率
        snc_val = dm.safe_float(df_Monitor['股市淨變動'].iloc[0]) if '股市淨變動' in df_Monitor.columns else 0
        stock_nc_str = f"+{dm.fmt_int(snc_val)}" if snc_val > 0 else dm.fmt_int(snc_val)
        if snc_val > 0: stock_nc_color = "#EF4444" 
        elif snc_val < 0: stock_nc_color = "#10B981"

        sv_val = df_Monitor['股市波動率'].iloc[0] if '股市波動率' in df_Monitor.columns else '0%'
        stock_vol_str = sv_val if isinstance(sv_val, str) and '%' in sv_val else dm.fmt_pct(sv_val)
        
        # 達成進度
        p_val = df_Monitor['達成進度'].iloc[0] if '達成進度' in df_Monitor.columns else '0%'
        pct_float = dm.safe_float(p_val)
        pct_float = pct_float / 100.0 if pct_float > 1 else pct_float
        
        # 曝險指標 E
        e_val = df_Monitor['曝險指標 E'].iloc[0] if '曝險指標 E' in df_Monitor.columns else '0%'
        lev_str = e_val if isinstance(e_val, str) and '%' in e_val else dm.fmt_pct(e_val)

    target = 0
    gap = 0

    if not df_C.empty:
        df_c = df_C.copy()
        first_col = df_c.columns[0]
        df_c[first_col] = df_c[first_col].astype(str).str.strip()
        df_c.set_index(first_col, inplace=True)
        col_val = df_c.columns[0]

        target = dm.safe_float(df_c.loc['短期財務目標', col_val]) if '短期財務目標' in df_c.index else 0
        gap = dm.safe_float(df_c.loc['短期財務目標差距', col_val]) if '短期財務目標差距' in df_c.index else 0

    # 第一排卡片：總資產、現金、NAV淨變動、NAV波動率
    row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
    with row1_col1: st.markdown(vis.render_simple_card('總資產', tot_asset_str), unsafe_allow_html=True)
    with row1_col2: st.markdown(vis.render_simple_card('現金', cash_str), unsafe_allow_html=True)
    with row1_col3: st.markdown(vis.render_simple_card('NAV淨變動', nav_nc_str, nav_nc_color), unsafe_allow_html=True)
    with row1_col4: st.markdown(vis.render_simple_card('NAV波動率', nav_vol_str), unsafe_allow_html=True)

    # 第二排卡片：股票市值、股市淨變動、股市波動率、達成進度
    row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)
    with row2_col1: st.markdown(vis.render_simple_card('股票市值', stock_value_str), unsafe_allow_html=True)
    with row2_col2: st.markdown(vis.render_simple_card('股市淨變動', stock_nc_str, stock_nc_color), unsafe_allow_html=True)
    with row2_col3: st.markdown(vis.render_simple_card('股市波動率', stock_vol_str), unsafe_allow_html=True)
    with row2_col4: st.markdown(vis.render_goal_progress_card(target, gap, pct_float), unsafe_allow_html=True)

    # 📅 今日判斷 & 市場狀態
    st.markdown("<h3 style='margin-top: 0.5rem; margin-bottom: 0.5rem;'>📅 今日判斷 & 市場狀態</h3>", unsafe_allow_html=True)

    monitor_bottom_dict = {}
    if not df_Monitor.empty:
        for i, row in df_Monitor.iterrows():
            if 'LDR' in row.values and '盤勢位置' in row.values:
                headers = row.astype(str).str.strip().tolist()
                if i + 1 < len(df_Monitor):
                    values = df_Monitor.iloc[i + 1].tolist()
                    monitor_bottom_dict = dict(zip(headers, values))
                break

    if monitor_bottom_dict:
        try:
            ldr_raw = str(monitor_bottom_dict.get('LDR', 'N/A'))
            risk_today = str(monitor_bottom_dict.get('今日風險等級', 'N/A'))
            cmd = str(monitor_bottom_dict.get('今日指令', 'N/A'))
            cmd = re.sub(r"【Debug.*?】", "", cmd, flags=re.DOTALL).strip()
            market_pos = str(monitor_bottom_dict.get('盤勢位置', 'N/A'))
            
            ldr_val_num = dm.safe_float(ldr_raw)
            ldr_ratio = ldr_val_num / 100.0 if ldr_val_num > 5 else ldr_val_num
            
            if ldr_ratio <= 1.0: ldr_status_txt, ldr_color = "黃金結構", "#10B981"
            elif ldr_ratio <= 1.05: ldr_status_txt, ldr_color = "#F59E0B"
            elif ldr_ratio < 1.08: ldr_status_txt, ldr_color = "過熱", "#EA580C"
            else: ldr_status_txt, ldr_color = "危險", "#EF4444"
            
            ldr_display = f"{ldr_val_num:.2f}%<div style='font-size: 1rem; line-height: 1.0; margin-top: 2px;'>{ldr_status_txt}</div>"

            # 曝險倍數狀態判定
            e_val_num = dm.safe_float(e_val)
            e_ratio = e_val_num / 100.0 if e_val_num > 5 else e_val_num
            
            if e_ratio < 1.10: e_status_txt, e_color = "安全", "#10B981"
            elif e_ratio <= 1.12: e_status_txt, e_color = "警戒", "#F59E0B"
            else: e_status_txt, e_color = "危險", "#EF4444"
            
            e_display = f"{lev_str}<div style='font-size: 1rem; line-height: 1.0; margin-top: 2px;'>{e_status_txt}</div>"

            raw_pledge = dm.safe_float(monitor_bottom_dict.get('總質押率', 0))
            pledge_val = raw_pledge * 100 if abs(raw_pledge) <= 5.0 else raw_pledge
            
            sheet_pledge_status = ""
            if not df_C.empty:
                 p_status_raw = dm.fuzzy_get(df_C.set_index(df_C.columns[0]), '質押率燈號')
                 if p_status_raw: sheet_pledge_status = str(p_status_raw).strip()

            if sheet_pledge_status:
                 p_status = sheet_pledge_status
                 if "安全" in p_status: p_color = "#10B981"
                 elif "謹慎" in p_status: p_color = "#0EA5E9"
                 elif "高警戒" in p_status: p_color = "#EA580C"
                 elif "警戒" in p_status: p_color = "#F59E0B"
                 elif "危險" in p_status: p_color = "#EF4444"
                 else: p_color = "#334155"
            else:
                if pledge_val < 30: p_status, p_color = "安全（絕對安全區）", "#10B981"
                elif pledge_val < 35: p_status, p_color = "謹慎可開火區", "#0EA5E9"
                elif pledge_val < 40: p_status, p_color = "警戒（火力鎖定區）", "#F59E0B"
                elif pledge_val < 45: p_status, p_color = "高警戒", "#EA580C"
                else: p_status, p_color = "危險", "#EF4444"
            
            pledge_display = f"{pledge_val:.2f}%<div style='font-size: 1rem; line-height: 1.0; margin-top: 2px; white-space: normal; word-break: break-word;'>{p_status}</div>"
            
            bias_val = str(monitor_bottom_dict.get('季線乖離', 'N/A'))
            
            vix_val, vix_status = "N/A", ""
            if not df_Market.empty:
                idx_col = df_Market.columns[0]
                vix_row = df_Market[df_Market[idx_col].astype(str).str.strip().str.upper() == 'VIX']
                if not vix_row.empty:
                    if len(df_Market.columns) >= 2:
                        vix_val = str(vix_row.iloc[0].iloc[1]).strip()
                    if len(df_Market.columns) >= 4:
                        vix_status = str(vix_row.iloc[0].iloc[3]).strip()

            risk_color = "#334155"
            if "紅" in risk_today: risk_color = "#EF4444"
            elif "橘" in risk_today: risk_color = "#EA580C"
            elif "黃" in risk_today: risk_color = "#F59E0B"
            elif "綠" in risk_today: risk_color = "#10B981"

            m_cols = st.columns(6)
            
            with m_cols[0]: st.markdown(vis.render_mini_metric("LDR", ldr_display, ldr_color), unsafe_allow_html=True)
            with m_cols[1]: st.markdown(vis.render_mini_metric("曝險倍數", e_display, e_color), unsafe_allow_html=True)
            with m_cols[2]:
                match = re.search(r"(.+?)\s*([\(（].+?[\)）])", risk_today)
                if match:
                    r_main = match.group(1).strip()
                    r_sub = match.group(2).strip()
                    r_sub_clean = re.sub(r"[（）\(\)]", "", r_sub)
                    risk_display_html = f"{r_main}<div style='font-size: 1rem; line-height: 1.0; margin-top: 2px; white-space: normal; word-break: break-word;'>{r_sub_clean}</div>"
                else: risk_display_html = risk_today
                st.markdown(vis.render_mini_metric("風險等級", risk_display_html, risk_color), unsafe_allow_html=True)
                
            with m_cols[3]: st.markdown(vis.render_mini_metric("質押率", pledge_display, p_color), unsafe_allow_html=True)
            with m_cols[4]:
                bias_display = "N/A"
                if bias_val != "N/A":
                        bv = dm.safe_float(bias_val)
                        bias_display = f"{bv:.2f}%"
                val_str = f"{market_pos}<div style='font-size: 1rem; line-height: 1.0; margin-top: 2px;'>{bias_display}</div>"
                st.markdown(vis.render_mini_metric("盤勢", val_str), unsafe_allow_html=True)
            with m_cols[5]:
                v_html = vix_status
                match = re.search(r"(.+?)\s*([\(（].+?[\)）])", vix_status, re.DOTALL)
                if match:
                    v_main = match.group(1).strip()
                    v_sub = match.group(2).strip()
                    v_sub_clean = re.sub(r"[（）\(\)]", "", v_sub).replace('\n', ' ')
                    v_html = f"{v_main}<div style='font-size: 1rem; line-height: 1.3; margin-top: 2px; white-space: normal; color: gray;'>{v_sub_clean}</div>"
                vix_display_html = f"{vix_val}<div style='font-size: 1rem; line-height: 1.2; margin-top: 2px;'>{v_html}</div>"
                st.markdown(vis.render_mini_metric("VIX", vix_display_html), unsafe_allow_html=True) 
            
            st.markdown(f"<div style='font-size:1.1em;color:gray;margin-top:2px;margin-bottom:2px'>📊 操作指令 (60日乖離: {bias_val})</div>", unsafe_allow_html=True)
            st.info(f"{cmd}")
            
            mindset_text = ""
            for i, row in df_Monitor.iterrows():
                if '心態短句' in row.values or '提醒' in row.values:
                    headers = row.astype(str).str.strip().tolist()
                    if i + 1 < len(df_Monitor):
                        values = df_Monitor.iloc[i + 1].tolist()
                        m_dict = dict(zip(headers, values))
                        mindset_col = next((c for c in m_dict.keys() if '心態' in str(c) or '提醒' in str(c)), None)
                        if mindset_col:
                            mindset_text = str(m_dict.get(mindset_col, '')).strip()
                    break
            
            if mindset_text:
                st.markdown(vis.render_mindset_card(mindset_text), unsafe_allow_html=True)
                
        except Exception as e: st.error(f"解析判斷數據時發生錯誤: {e}")
    else: st.warning('總覽數據載入失敗。請檢查 Secrets 設定或試算表網址。')
    st.markdown("---")

# === 執行局部無感跳動區塊 ===
render_live_monitoring_fragment()


# ==========================================
# 2. 持股分析 (靜態區，不隨Fragment重載閃爍)
# ==========================================
st.header('2. 持股分析')
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("### 📝 持股明細") 
    if not df_A.empty:
        df_show = df_A.copy()
        if st.session_state['live_prices']:
            df_show['即時價'] = df_show['股票'].map(st.session_state['live_prices']).fillna('')
        
        for c in ['持有數量（股）', '市值（元）', '浮動損益']: 
            if c in df_show.columns: df_show[c] = df_show[c].apply(dm.fmt_int)
        for c in ['平均成本', '收盤價', '即時價']:
            if c in df_show.columns: df_show[c] = df_show[c].apply(dm.fmt_money)
            
        height_val = (len(df_show) + 1) * 35 + 20
        st.dataframe(df_show, use_container_width=True, height=height_val, hide_index=True)

with c2:
    st.markdown("<h3 style='text-align: center;'>🍰 資產配置</h3>", unsafe_allow_html=True) 
    fig = vis.plot_asset_allocation(df_B)
    if fig:
        st.plotly_chart(fig, use_container_width=True)


# ==========================================
# 3. 交易紀錄與淨值 (靜態區)
# ==========================================
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
        total = df_calc['淨收／支出'].apply(dm.safe_float).sum() if '淨收／支出' in df_calc.columns else 0
        c_a, c_b = st.columns(2)
        c_a.metric("篩選淨額", dm.fmt_money(total))
        c_b.markdown(f"**筆數：** {len(df_calc)}")
        df_view = df_calc.drop(columns=['dt'], errors='ignore').copy()
        if '日期' in df_view.columns: df_view['日期'] = df_view['日期'].apply(dm.fmt_date)
        for c in ['淨收／支出', '累積現金', '成交價']:
            if c in df_view.columns: df_view[c] = df_view[c].apply(dm.fmt_money)
        if '數量' in df_view.columns: df_view['數量'] = df_view['數量'].apply(dm.fmt_int)
        st.dataframe(df_view, use_container_width=True, height=400)
        if not df_calc.empty: st.caption(f"📅 {df_calc['dt'].min().date()} ~ {df_calc['dt'].max().date()}")

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
        total = df_calc['已實現損益'].apply(dm.safe_float).sum() if '已實現損益' in df_calc.columns else 0
        st.metric("總實現損益", dm.fmt_money(total))
        df_view = df_calc.drop(columns=['dt'], errors='ignore').copy()
        if d_col: df_view[d_col] = df_view[d_col].apply(dm.fmt_date)
        for c in ['已實現損益', '投資成本', '帳面收入', '成交均價']:
             if c in df_view.columns: df_view[c] = df_view[c].apply(dm.fmt_money)
        st.dataframe(df_view, use_container_width=True, height=400)

with t3:
    fig = vis.plot_nav_trend(df_F)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("詳細數據"):
            df_calc = df_F.copy()
            d_col = next((c for c in df_calc.columns if '日期' in c), '日期')
            df_calc['dt'] = pd.to_datetime(df_calc[d_col], errors='coerce')
            df_disp = df_calc.sort_values('dt', ascending=False).drop(columns=['dt'], errors='ignore').copy()
            df_disp['日期'] = df_disp['日期'].apply(dm.fmt_date)
            for c in ['實質NAV', '股票市值', '現金']:
                if c in df_disp.columns: df_disp[c] = df_disp[c].apply(dm.fmt_money)
            st.dataframe(df_disp, use_container_width=True)
            if not df_calc.empty: st.caption(f"📅 紀錄: {df_calc['dt'].min().date()} ~ {df_calc['dt'].max().date()}")

st.markdown('---')

# ==========================================
# 4. 財富藍圖 (靜態區)
# ==========================================
st.header('4. 財富藍圖')
if not df_G.empty:
    try:
        all_rows = [df_G.columns.tolist()] + df_G.values.tolist()
        current_title = None
        current_data = []
        found_sections = False 
        
        for row in all_rows:
            first_cell = str(row[0]).strip()
            if first_cell.startswith(('一、', '二、', '三、', '四、', '五、')):
                found_sections = True
                if current_title:
                    title_match = re.search(r"(.+?)\s*[（\(](.+)[）\)]", current_title)
                    if title_match:
                        main_t = title_match.group(1).strip()
                        sub_t = title_match.group(2).strip()
                        st.markdown(f"### {main_t}")
                        st.markdown(f"<div style='font-size: 0.9em; color: gray; margin-top: -0.5rem; margin-bottom: 0.8rem;'>（{sub_t}）</div>", unsafe_allow_html=True)
                    else:
                        st.subheader(current_title)
                        
                    if len(current_data) > 0:
                        headers = current_data[0]
                        body = current_data[1:] if len(current_data) > 1 else []
                        u_heads = []
                        seen = {}
                        for h in headers:
                            h_str = str(h).strip()
                            if not h_str: h_str = "-" 
                            if h_str in seen: seen[h_str] += 1; u_heads.append(f"{h_str}_{seen[h_str]}")
                            else: seen[h_str] = 0; u_heads.append(h_str)
                        if body:
                            st.dataframe(pd.DataFrame(body, columns=u_heads), use_container_width=True, hide_index=True)
                current_title = first_cell
                current_data = []
            elif any(str(c).strip() for c in row):
                if current_title is not None:
                    current_data.append(row)
        
        # Render last
        if current_title:
            title_match = re.search(r"(.+?)\s*[（\(](.+)[）\)]", current_title)
            if title_match:
                main_t = title_match.group(1).strip()
                sub_t = title_match.group(2).strip()
                st.markdown(f"### {main_t}")
                st.markdown(f"<div style='font-size: 0.9em; color: gray; margin-top: -0.5rem; margin-bottom: 0.8rem;'>（{sub_t}）</div>", unsafe_allow_html=True)
            else:
                st.subheader(current_title)
            
            if len(current_data) > 0:
                headers = current_data[0]
                body = current_data[1:] if len(current_data) > 1 else []
                u_heads = []
                seen = {}
                for h in headers:
                    h_str = str(h).strip()
                    if not h_str: h_str = "-" 
                    if h_str in seen: seen[h_str] += 1; u_heads.append(f"{h_str}_{seen[h_str]}")
                    else: seen[h_str] = 0; u_heads.append(h_str)
                if body:
                    st.dataframe(pd.DataFrame(body, columns=u_heads), use_container_width=True, hide_index=True)
        
        if not found_sections:
            st.dataframe(df_G, use_container_width=True)

    except:
        st.dataframe(df_G, use_container_width=True)
else:
    st.info("無財富藍圖資料")
