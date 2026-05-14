import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import data_manager as dm

# --- CSS 樣式 ---
def get_custom_css():
    return """
    <style>
    /* 1. 調整頁面頂部留白 */
    .block-container {
        padding-top: 5rem;
        padding-bottom: 2rem;
    }

    html, body, [class*="stApp"] { font-size: 16px; }
    h1 { font-size: 2.2em; margin-bottom: 0.5rem; }
    h2 { font-size: 1.6em; padding-top: 0.5rem; }
    h3 { font-size: 1.4em; }

    /* 表格設定：隱藏表頭 (針對核心資產優化) */
    [data-testid="stDataFrame"] thead {
        display: none;
    }

    /* 側邊欄按鈕樣式 */
    div[data-testid="stSidebar"] .stButton button {
        width: 100%; height: 45px; margin-bottom: 10px; border: 1px solid #ccc;
    }

    /* 進度條顏色 */
    .stProgress > div > div > div > div {
        background-color: #00b4d8;
    }

    /* 自訂指標卡片樣式 (用於曝險指標優化) */
    .custom-metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 12px;
        text-align: center;
        height: 100%; /* 嘗試填滿高度 */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .metric-label {
        font-size: 0.9em;
        color: #6c757d;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 2.0em; /* 稍微加大數值 */
        font-weight: bold;
        color: #212529;
        line-height: 1.1;
    }
    .metric-badge {
        display: block; /* 改為區塊元素以滿版 */
        width: 100%;    /* 設定寬度為 100% */
        padding: 6px 0; /* 增加垂直 padding */
        border-radius: 6px;
        color: white;
        font-size: 1.1em; /* 加大字體 */
        font-weight: bold;
        margin-bottom: 10px; /* 增加下方間距 */
    }

    /* 心態提醒卡片樣式 */
    .mindset-card {
        background-color: #e8f4f8; /* 淺藍色底 */
        border-left: 5px solid #00b4d8; /* 左側藍色線條 */
        padding: 15px;
        border-radius: 5px;
        margin-top: 15px; /* 與上方卡片保持距離 */
        color: #0f5132;
        font-size: 1.0em;
        display: flex;
        align-items: center;
        width: 100%;
    }
    </style>
    """

# --- 圖表繪製 ---
def plot_asset_allocation(df_B):
    """繪製資產配置圓餅圖"""
    if not df_B.empty and '市值（元）' in df_B.columns:
        df_B['num'] = df_B['市值（元）'].apply(dm.safe_float)
        chart_data = df_B[(df_B['num'] > 0) & (~df_B['股票'].str.contains('總資產|Total', na=False))]
        if not chart_data.empty:
            color_discrete_sequence = ['#0077b6', '#00b4d8', '#90e0ef', '#caf0f8']
            fig = px.pie(
                chart_data, 
                values='num', 
                names='股票',
                color_discrete_sequence=color_discrete_sequence
            )
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            return fig
    return None

def plot_nav_trend(df_F):
    """繪製戰略級 NAV 趨勢與淨變動複合圖 (Light Tech Blue Edition)"""
    if not df_F.empty:
        df_calc = df_F.copy()
        if '實質NAV' in df_calc.columns and '日期' in df_calc.columns:
            df_calc['dt'] = pd.to_datetime(df_calc['日期'], errors='coerce')
            df_calc['nav'] = df_calc['實質NAV'].apply(dm.safe_float)
            
            if 'NAV淨變動' in df_calc.columns:
                df_calc['net_change'] = df_calc['NAV淨變動'].apply(dm.safe_float)
            elif '當日淨變動' in df_calc.columns:
                df_calc['net_change'] = df_calc['當日淨變動'].apply(dm.safe_float)
            else:
                df_calc['net_change'] = 0.0
                
            df_chart = df_calc.sort_values('dt').reset_index(drop=True)
            df_chart['SMA20'] = df_chart['nav'].rolling(window=20, min_periods=1).mean()
            
            BG_COLOR = '#FFFFFF'
            GRID_COLOR = '#F1F5F9'
            COLOR_RISE = '#FF0000'
            COLOR_FALL = '#009900'
            COLOR_NAV_MAIN = '#00B4D8'
            COLOR_NAV_FILL = 'rgba(0, 180, 216, 0.08)'
            COLOR_SMA = '#94A3B8'
            TEXT_COLOR = '#334155'
            MODERN_FONT = "Arial, 'Heiti TC', 'Microsoft JhengHei', sans-serif"
            
            colors = [COLOR_RISE if val > 0 else COLOR_FALL for val in df_chart['net_change']]
            df_chart['hover_color'] = colors

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

            fig.add_trace(
                go.Scatter(
                    x=df_chart['dt'], y=df_chart['nav'], name="每日淨值", fill='tozeroy', mode='lines', 
                    line=dict(color=COLOR_NAV_MAIN, width=2.5, shape='spline', smoothing=0.8),
                    fillcolor=COLOR_NAV_FILL,
                    customdata=df_chart[['net_change', 'SMA20', 'hover_color']].values,
                    hovertemplate='<b>日期：%{x|%Y-%m-%d}</b><br><br><b>每日淨值：</b> %{y:,.0f}<br><b>淨值變化：</b> <span style="color:%{customdata[2]}">%{customdata[0]:+,.0f}</span><br><b>NAV 20MA：</b> %{customdata[1]:,.0f}<extra></extra>'
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=df_chart['dt'], y=df_chart['SMA20'], name="NAV 20MA", mode='lines', line=dict(color=COLOR_SMA, width=1.5, dash='dash'), hoverinfo='skip'),
                row=1, col=1
            )

            fig.add_trace(
                go.Bar(x=df_chart['dt'], y=df_chart['net_change'], name="淨值變化", marker_color=colors, opacity=0.75, marker_line_width=0, hoverinfo='skip'),
                row=2, col=1
            )

            fig.update_layout(
                template='plotly_white', hovermode="x", margin=dict(t=40, b=10, l=10, r=10),
                plot_bgcolor=BG_COLOR, paper_bgcolor=BG_COLOR,
                font=dict(family=MODERN_FONT, size=13, color=TEXT_COLOR),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family=MODERN_FONT, color=TEXT_COLOR)),
                hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=COLOR_NAV_MAIN, font_size=14, font_family=MODERN_FONT, font_color="#334155")
            )

            fig.update_xaxes(showgrid=False, showspikes=True, spikemode="across", spikesnap="cursor", spikedash="solid", spikethickness=1, spikecolor="#CBD5E1", showline=True, linecolor=GRID_COLOR, row=1, col=1)
            fig.update_xaxes(showgrid=False, showline=True, linecolor=GRID_COLOR, row=2, col=1)
            
            min_nav = df_chart['nav'].min()
            max_nav = df_chart['nav'].max()
            y_bottom = 1400000 if min_nav > 1400000 else min_nav * 0.95
            y_top = max_nav * 1.05

            if max_nav < 5000000: nav_dtick = 200000
            elif max_nav < 10000000: nav_dtick = 300000
            else: nav_dtick = 500000

            fig.update_yaxes(range=[y_bottom, y_top], title_font=dict(family=MODERN_FONT, color=TEXT_COLOR, size=12), tickformat=",.0f", dtick=nav_dtick, showgrid=True, gridwidth=1, gridcolor=GRID_COLOR, showline=True, linecolor=GRID_COLOR, row=1, col=1)
            fig.update_yaxes(showticklabels=False, showgrid=False, zeroline=True, zerolinecolor='#CBD5E1', zerolinewidth=1.5, row=2, col=1)

            return fig
    return None

def plot_wealth_trajectory(df_F=None):
    """繪製 NEGENTROPIC ATARAXIA 財富路徑導航圖 (雙視圖狙擊系統，畫布相對座標解耦)"""
    
    # 嚴格依照圖表上的可見 X 軸節點
    years = [2026, 2027, 2028, 2029, 2030, 2033, 2035, 2036, 2038, 2039, 2040]
    
    # 保守路徑 (15%) - 藍線
    nav_15 =   [2.9, 3.9, 4.8, 5.7, 6.6, 10.2, 13.7, 15.7, 19.0, 21.7, 24.2]
    text_15 =  ['2.9M', '3.9M', '', '5.7M', '6.6M', '10.2M', '13.7M', '15.7M', '19.0M', '21.7M', '24.2M']
    
    # 基準路徑 (17.5%) - 綠線
    nav_175 =  [2.9, 4.6, 5.5, 7.0, 8.1, 13.0, 17.5, 20.0, 30.0, 33.8, 36.2]
    text_175 = ['', '', '', '', '8.1M', '', '17.5M', '20.0M', '30.0M', '33.8M', '36.2M']
    
    # 野心路徑 (20%) - 紅線
    nav_20 =   [2.9, 5.1, 6.8, 8.6, 10.5, 18.6, 27.1, 37.0, 57.0, 63.6, 68.7]
    text_20 =  ['', '5.1M', '', '8.6M', '10.5M', '18.6M', '27.1M', '37.0M', '57.0M', '63.6M', '68.7M']

    MODERN_FONT = "Arial, 'Heiti TC', 'Microsoft JhengHei', sans-serif"

    fig = go.Figure()

    # 0. 潛力區間填色 (獨立圖層)
    fig.add_trace(go.Scatter(
        x=years + years[::-1],
        y=nav_20 + nav_15[::-1],
        fill='toself',
        fillcolor='rgba(44, 160, 44, 0.12)', # 淺綠色潛力區間
        line=dict(color='rgba(255,255,255,0)'),
        name='財富潛力區間 (15%-20%)',
        hoverinfo='skip',
        showlegend=True
    ))

    # 1. 野心路徑 (20%) - 紅色實線，Hover 最上方
    fig.add_trace(go.Scatter(
        x=years, y=nav_20,
        name='野心路徑 (年化 20%)',
        mode='lines+markers+text',
        text=text_20, textposition="top left",
        line=dict(color='#D62728', width=2),
        marker=dict(size=6, color='#D62728'),
        textfont=dict(color='#D62728', size=10, family=MODERN_FONT),
        hovertemplate='<b>%{x} 野心</b>: %{y:.1f}M<extra></extra>'
    ))

    # 2. 基準路徑 (17.5%) - 綠色實線，Hover 中間
    fig.add_trace(go.Scatter(
        x=years, y=nav_175,
        name='基準路徑 (年化 17.5%)',
        mode='lines+markers+text',
        text=text_175, textposition="top center",
        line=dict(color='#2CA02C', width=3),
        marker=dict(size=8, color='#2CA02C', line=dict(color='white', width=1)),
        textfont=dict(color='#2CA02C', size=11, family=MODERN_FONT),
        hovertemplate='<b>%{x} 基準</b>: %{y:.1f}M<extra></extra>'
    ))

    # 3. 保守路徑 (15%) - 藍色實線，Hover 最下方
    fig.add_trace(go.Scatter(
        x=years, y=nav_15,
        name='保守路徑 (年化 15%)',
        mode='lines+markers+text',
        text=text_15, textposition="bottom right",
        line=dict(color='#1F77B4', width=2),
        marker=dict(size=6, color='#1F77B4'),
        textfont=dict(color='#1F77B4', size=10, family=MODERN_FONT),
        hovertemplate='<b>%{x} 保守</b>: %{y:.1f}M<extra></extra>'
    ))

    # 4. 起點紫點
    fig.add_trace(go.Scatter(
        x=[2026], y=[2.887], name='實際 NAV (2026 起點)', mode='markers',
        marker=dict(size=10, color='#7C3AED'), hovertemplate='<b>起點</b>: 2.887M<extra></extra>'
    ))

    # ==========================================
    # ⚡ 戰略更新：實時實際戰線 (Real-Time NAV Overlay)
    # ==========================================
    if df_F is not None and not df_F.empty:
        df_real = df_F.copy()
        date_col = next((c for c in df_real.columns if '日期' in c), None)
        if date_col and '實質NAV' in df_real.columns:
            df_real['dt'] = pd.to_datetime(df_real[date_col], errors='coerce')
            df_real = df_real.dropna(subset=['dt', '實質NAV'])
            
            if not df_real.empty:
                df_real = df_real.sort_values('dt')
                df_real['frac_year'] = df_real['dt'].dt.year + (df_real['dt'].dt.dayofyear - 1) / 365.25
                df_real['nav_m'] = df_real['實質NAV'].apply(dm.safe_float) / 1000000.0
                df_real['date_str'] = df_real['dt'].dt.strftime('%Y-%m-%d')
                
                fig.add_trace(go.Scatter(
                    x=df_real['frac_year'], y=df_real['nav_m'],
                    name='⚡ 實際戰線 (Real NAV)',
                    mode='lines+markers',
                    line=dict(color='#F59E0B', width=3.5), # 發光琥珀金
                    marker=dict(size=6, color='#F59E0B', line=dict(color='white', width=1)),
                    customdata=df_real['date_str'],
                    hovertemplate='<b>%{customdata} 實際</b>: %{y:.3f}M<extra></extra>'
                ))
                
                last_x = df_real['frac_year'].iloc[-1]
                last_y = df_real['nav_m'].iloc[-1]
                fig.add_trace(go.Scatter(
                    x=[last_x], y=[last_y],
                    name='最新定位點',
                    mode='markers+text',
                    text=[f"⚡ {last_y:.2f}M"],
                    textposition="top left",
                    marker=dict(size=14, symbol='star', color='#F59E0B', line=dict(color='white', width=1)),
                    textfont=dict(color='#F59E0B', size=12, family=MODERN_FONT, weight='bold'),
                    hoverinfo='skip',
                    showlegend=False
                ))

    # --- 戰略解耦：畫布相對座標 (yref='paper') ---
    # 將所有標籤與色塊從資料 Y 軸解放，讓它們固定在圖表的實體頂端與底端，不受縮放影響。

    # 高度交錯設定 (yref="paper"，1.0 為圖表框上緣，超過 1.0 為上方留白區)
    y_high = 1.10
    y_low = 1.02

    fig.add_shape(type="rect", x0=2026, y0=0, x1=2027.5, y1=1, yref="paper", fillcolor="#E5F3FF", line_width=0, layer="below")
    fig.add_annotation(x=2026.75, y=y_high, yref="paper", text="<b>Phase 1 窒息期</b><br>2026 Q1-2027 Q2<br>死守現金與氧氣", showarrow=False, font=dict(size=10, color="#003366"))

    fig.add_shape(type="rect", x0=2027.5, y0=0, x1=2028.5, y1=1, yref="paper", fillcolor="#E5F9E5", line_width=0, layer="below")
    fig.add_annotation(x=2028.0, y=y_low, yref="paper", text="<b>Phase 2 注資期</b><br>2027 Q3-2027 Q4<br>第一次注資", showarrow=False, font=dict(size=10, color="#004D00"))

    fig.add_shape(type="rect", x0=2028.5, y0=0, x1=2030, y1=1, yref="paper", fillcolor="#FFFBE6", line_width=0, layer="below")
    fig.add_annotation(x=2029.25, y=y_high, yref="paper", text="<b>Phase 3 加速期</b><br>2028-2029<br>複利啟動與積累", showarrow=False, font=dict(size=10, color="#664D00"))

    fig.add_shape(type="rect", x0=2030, y0=0, x1=2034, y1=1, yref="paper", fillcolor="#F2E6FF", line_width=0, layer="below")
    fig.add_annotation(x=2032.0, y=y_low, yref="paper", text="<b>Phase 4 隱形加速</b><br>2030-2033<br>資本效應放大期", showarrow=False, font=dict(size=10, color="#330066"))

    fig.add_shape(type="rect", x0=2034, y0=0, x1=2040, y1=1, yref="paper", fillcolor="#FFE6E6", line_width=0, layer="below")
    fig.add_annotation(x=2037.0, y=y_high, yref="paper", text="<b>Phase 5 自由區域</b><br>2034-2040<br>高資本自主導向", showarrow=False, font=dict(size=10, color="#660000"))

    # --- 像素級偏移事件標註 (Pixel Offset) ---
    # 利用 ax=0, ay=-80，讓箭頭固定在資料點的上方 80 像素處，不會因縮放而跑到畫面外
    events = [
        dict(x=2027, y_data=5.1, text="<b>2027 Q4 注資</b><br>約 710K-910K", color="#FF6600", symbol="star"),
        dict(x=2029, y_data=8.6, text="<b>2029 Q4 注資</b><br>約 550K-900K", color="#0066CC", symbol="star"),
        dict(x=2033, y_data=18.6, text="<b>2033 加速期</b><br>跨越千萬門檻", color="#9933CC", symbol="arrow-down")
    ]

    for ev in events:
        fig.add_annotation(
            x=ev['x'], y=ev['y_data'],
            ax=0, ay=-70, # 固定向上偏移 70 像素
            text=ev['text'], showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor=ev['color'], opacity=0.8,
            font=dict(color=ev['color'], size=11, family=MODERN_FONT),
            bgcolor="rgba(255,255,255,0.8)", bordercolor=ev['color'], borderwidth=1, borderpad=4
        )
        if ev['symbol'] == 'star':
            fig.add_trace(go.Scatter(x=[ev['x']], y=[ev['y_data']], mode='markers', marker=dict(symbol='star', size=14, color=ev['color']), hoverinfo='skip', showlegend=False))

    # 綠色車貸/分期結束標註 (像素級偏移)
    fig.add_annotation(
        x=2027, y=2.9, ax=-40, ay=50, # 固定向左下偏移
        text="<b>2027/05</b><br>車貸結束<br>現金流<br>+10K/月", showarrow=True, arrowhead=2, arrowcolor="#2CA02C", arrowwidth=1.5, opacity=0.8,
        font=dict(color="#2CA02C", size=9, family=MODERN_FONT),
        bgcolor="rgba(255,255,255,0.8)", bordercolor="#2CA02C", borderwidth=1, borderpad=4
    )
    fig.add_annotation(
        x=2028, y=4.8, ax=-40, ay=50,
        text="<b>2027/07</b><br>分期結束<br>現金流<br>+2.8K/月", showarrow=True, arrowhead=2, arrowcolor="#2CA02C", arrowwidth=1.5, opacity=0.8,
        font=dict(color="#2CA02C", size=9, family=MODERN_FONT),
        bgcolor="rgba(255,255,255,0.8)", bordercolor="#2CA02C", borderwidth=1, borderpad=4
    )

    # --- 底部里程碑區塊 (yref='paper' 固定於圖表底端下方) ---
    y_ms = -0.15 # 圖表框下緣再往下 15%
    fig.add_annotation(x=2025.5, y=y_ms, yref="paper", text="<b>關鍵里程碑</b><br>(目標節點)", showarrow=False, bgcolor="#F1F5F9", bordercolor="#CBD5E1", borderwidth=1, borderpad=6, font=dict(size=10))
    fig.add_annotation(x=2027, y=y_ms, yref="paper", text="<b>2026</b><br><b>300 萬</b><br>可觸及區<br>站穩 300 萬穩態", showarrow=False, bgcolor="#E5F9E5", bordercolor="#2CA02C", borderwidth=1, borderpad=6, font=dict(size=10))
    fig.add_annotation(x=2028.5, y=y_ms, yref="paper", text="<b>2027</b><br><b>500 萬</b><br>臨界門檻<br>第一階 -> 第二階", showarrow=False, bgcolor="#FFF4E6", bordercolor="#FF6600", borderwidth=1, borderpad=6, font=dict(size=10))
    fig.add_annotation(x=2031.5, y=y_ms, yref="paper", text="<b>2030</b><br><b>1,000 萬</b><br>射程內<br>飛輪完成．千萬合理射程", showarrow=False, bgcolor="#E5F3FF", bordercolor="#1F77B4", borderwidth=1, borderpad=6, font=dict(size=10))
    fig.add_annotation(x=2035, y=y_ms, yref="paper", text="<b>2033</b><br>千萬後區間<br>主場開始<br>資本效應放大", showarrow=False, bgcolor="#F2E6FF", bordercolor="#9933CC", borderwidth=1, borderpad=6, font=dict(size=10))
    fig.add_annotation(x=2039, y=y_ms, text="<b>2040</b><br>美元百萬<br>高資本自主<br>自由區域", yref="paper", showarrow=False, bgcolor="#FFE6E6", bordercolor="#D62728", borderwidth=1, borderpad=6, font=dict(size=10))

    fig.update_layout(
        title=dict(
            text="<b>NEGENTROPIC ATARAXIA 10.0 財富路徑整合圖：保守 vs 野心 (2026 起點 · 2025–2040)</b><br><span style='font-size:12px; color:#64748B;'>起點：2026/04/24 NAV 約 NT$2,887,023 | 年化 15%–20% 區間 | 每年淨投入約 NT$150,000<br>兩次關鍵注資：2027 Q4 約 NT$710,000–910,000；2029 Q4 約 NT$550,000–900,000<br>風控原則：E < 112、LDR < 115、質押率長期 < 35%</span>",
            font=dict(size=16, family=MODERN_FONT), x=0.5, xanchor='center', y=0.98, yanchor='top'
        ),
        template='plotly_white', hovermode="x unified",
        margin=dict(t=200, b=120, l=50, r=50), # 釋放充足的上下外圍空間給 Paper 標註
        font=dict(family=MODERN_FONT, color='#334155'),
        legend=dict(
            orientation="v", yanchor="top", y=0.88, xanchor="left", x=0.02,
            bgcolor="rgba(255,255,255,0.9)", bordercolor="#E2E8F0", borderwidth=1
        ),
        # --- 雙視角切換器 (Tactical Optics) ---
        updatemenus=[
            dict(
                type="buttons",
                direction="right", # 校準為正確的參數 "right"
                x=0.5, y=1.20, # 置中於標題下方
                xanchor="center", yanchor="bottom",
                showactive=True,
                buttons=list([
                    dict(
                        label="🗺️ 戰略全景 (2025-2040)",
                        method="relayout",
                        args=[{"xaxis.range": [2024.5, 2040.5], "yaxis.range": [0, 75]}]
                    ),
                    dict(
                        label="🎯 近期戰區 (2025-2032)",
                        method="relayout",
                        args=[{"xaxis.range": [2024.5, 2032.5], "yaxis.range": [0, 22]}] # 壓縮 Y 軸，讓前期破局點極度清晰
                    )
                ])
            )
        ],
        plot_bgcolor='#FFFFFF', paper_bgcolor='#FFFFFF',
        xaxis_title="", yaxis_title="總資產 NAV (百萬 TWD)",
        height=850
    )

    fig.update_xaxes(showgrid=True, gridcolor='#F1F5F9', tickvals=list(range(2025, 2041)), showline=True, linecolor='#CBD5E1', range=[2024.5, 2040.5])
    # 預設為全景視角
    fig.update_yaxes(showgrid=True, gridcolor='#F1F5F9', showline=True, linecolor='#CBD5E1', zeroline=False, range=[0, 75], dtick=10)

    return fig

# --- HTML 卡片產生器 ---
def render_risk_metric_card(risk_text, lev_value, style_dict):
    return f"""
    <div class='custom-metric-card'>
        <div class='metric-badge' style='background-color: {style_dict['bg']}; color: {style_dict['t']};'>
            {style_dict['e']} {risk_text}
        </div>
        <div class='metric-label'>曝險倍數</div>
        <div class='metric-value'>{lev_value:.2f}</div>
    </div>
    """

def render_goal_progress_card(target, gap, pct):
    return f"""
    <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:10px; border:1px solid #e9ecef; height: 100%; display: flex; flex-direction: column; justify-content: center;">
        <div style="font-size:1.0em; color:#6c757d; margin-bottom:5px;">達成進度</div>
        <div style="font-size:2.2em; font-weight:bold; color:#007BFF; line-height:1.1;">
            {pct*100:.1f}%
        </div>
        <div style="margin-top:8px; font-size:0.85em; display:flex; justify-content:space-between; color:#495057;">
            <span>目標: <b>{dm.fmt_int(target)}</b></span>
        </div>
          <div style="text-align:right; font-size:0.8em; color:#e63946; margin-top:2px;">
            (差 {dm.fmt_int(gap)})
        </div>
    </div>
    """

def render_house_plan_card(r_display, dp_target, est_year):
    return f"""
    <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:10px; border:1px solid #e9ecef; height: 100%; display: flex; flex-direction: column; justify-content: center;">
        <div style="font-size:1.0em; color:#6c757d; margin-bottom:5px;">房屋準備度 R</div>
        <div style="font-size:2.2em; font-weight:bold; color:#00b4d8; line-height:1.1;">
            {r_display}
        </div>
        <div style="margin-top:8px; font-size:0.85em; display:flex; justify-content:space-between; color:#495057;">
            <span>頭期款: <b>{dm.fmt_int(dp_target)}</b></span>
        </div>
          <div style="text-align:right; font-size:0.8em; color:#6c757d; margin-top:2px;">
            (預估 {est_year} 年)
        </div>
    </div>
    """

def render_simple_card(title, value, value_color="#212529"):
    """通用數值展示卡片"""
    return f"""
    <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:10px; border:1px solid #e9ecef; height: 100%; display: flex; flex-direction: column; justify-content: center;">
        <div style="font-size:1.0em; color:#6c757d; margin-bottom:5px;">{title}</div>
        <div style="font-size:2.2em; font-weight:bold; color:{value_color}; line-height:1.1;">
            {value}
        </div>
    </div>
    """

def render_mindset_card(mindset_text):
    return f"""
    <div class="mindset-card">
        💡 <b>心態提醒：</b> {mindset_text}
    </div>
    """

def render_mini_metric(label, value, color="black"):
    return f"""
    <div style='margin-bottom:0px;'>
        <div style='font-size:1.1rem; color:gray; margin-bottom:2px; white-space: nowrap;'>{label}</div>
        <div style='font-size:1.8rem; font-weight:bold; color:{color}; line-height:1.2; white-space: normal; word-break: break-word;'>{value}</div>
    </div>
    """
