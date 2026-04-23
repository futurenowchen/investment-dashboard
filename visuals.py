import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
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
            # 使用更沉穩的科技藍色系
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
            
            # 取出每日淨變動作為波動柱狀圖
            if 'NAV淨變動' in df_calc.columns:
                df_calc['net_change'] = df_calc['NAV淨變動'].apply(dm.safe_float)
            elif '當日淨變動' in df_calc.columns:
                df_calc['net_change'] = df_calc['當日淨變動'].apply(dm.safe_float)
            else:
                df_calc['net_change'] = 0.0
                
            df_chart = df_calc.sort_values('dt').reset_index(drop=True)
            
            # 新增戰略生命線：20日移動平均 (這是使用者自身 NAV 的月線)
            df_chart['SMA20'] = df_chart['nav'].rolling(window=20, min_periods=1).mean()
            
            # === 清爽科技藍配色設定 (Light Tech Cyan Palette) ===
            BG_COLOR = '#FFFFFF'          # 純白基底，融入網頁
            GRID_COLOR = '#F1F5F9'        # 極淺灰網格線 (Slate 100)
            COLOR_RISE = '#EF4444'        # 亮紅 (台股漲)
            COLOR_FALL = '#10B981'        # 翠綠 (台股跌)
            COLOR_NAV_MAIN = '#00B4D8'    # 科技青
            COLOR_NAV_FILL = 'rgba(0, 180, 216, 0.08)' # 底部微光
            COLOR_SMA = '#94A3B8'         # 戰略灰 (Slate 400)
            TEXT_COLOR = '#334155'        # 深灰字體 (Slate 700)
            
            colors = [COLOR_RISE if val > 0 else COLOR_FALL for val in df_chart['net_change']]

            # 建立上下分離的 Subplots (7:3 比例)
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03,
                row_heights=[0.75, 0.25]
            )

            # 1. 主圖：NAV 折線面積圖 (Row 1)
            fig.add_trace(
                go.Scatter(
                    x=df_chart['dt'],
                    y=df_chart['nav'],
                    name="每日淨值", # 精簡命名
                    fill='tozeroy',
                    mode='lines', 
                    line=dict(
                        color=COLOR_NAV_MAIN, 
                        width=2.5, 
                        shape='spline', # 平滑曲線
                        smoothing=0.8
                    ),
                    fillcolor=COLOR_NAV_FILL,
                    hovertemplate='<b>%{y:,.0f}</b><extra></extra>' # 移除贅字，統一日期待在 Header
                ),
                row=1, col=1
            )
            
            # 1.1 主圖：20日移動平均線 (Row 1)
            fig.add_trace(
                go.Scatter(
                    x=df_chart['dt'],
                    y=df_chart['SMA20'],
                    name="NAV 20MA",
                    mode='lines',
                    line=dict(color=COLOR_SMA, width=1.5, dash='dash'),
                    hovertemplate='<b>%{y:,.0f}</b><extra></extra>'
                ),
                row=1, col=1
            )

            # 2. 副圖：動能底槽柱狀圖 (Row 2)
            fig.add_trace(
                go.Bar(
                    x=df_chart['dt'],
                    y=df_chart['net_change'],
                    name="淨值變化",
                    marker_color=colors,
                    opacity=0.75, 
                    marker_line_width=0, 
                    hovertemplate='<b>%{y:,.0f}</b><extra></extra>'
                ),
                row=2, col=1
            )

            # 版面優化設定 (Light Vibe)
            fig.update_layout(
                template='plotly_white', # 改為亮色主題
                hovermode="x unified",
                margin=dict(t=40, b=10, l=10, r=10),
                plot_bgcolor=BG_COLOR,
                paper_bgcolor=BG_COLOR,
                font=dict(family="Courier New, monospace", size=12, color=TEXT_COLOR),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(color=TEXT_COLOR)
                ),
                hoverlabel=dict(
                    bgcolor="#FFFFFF",
                    bordercolor=COLOR_NAV_MAIN,
                    font_size=13,
                    font_family="Courier New, monospace",
                    font_color="#334155"
                )
            )

            # X軸：共用設定
            fig.update_xaxes(
                showgrid=False, 
                showspikes=True, 
                spikemode="across",
                spikesnap="cursor",
                spikedash="solid",
                spikethickness=1,
                spikecolor="#CBD5E1", # 淺灰十字準線
                showline=True,
                linecolor=GRID_COLOR,
                row=1, col=1
            )
            fig.update_xaxes(
                showgrid=False, 
                showline=True,
                linecolor=GRID_COLOR,
                row=2, col=1
            )
            
            # 戰略 Y 軸截斷邏輯：以 140 萬為底部基準線，若淨值低於 140 萬則動態下移
            min_nav = df_chart['nav'].min()
            y_bottom = 1400000 if min_nav > 1400000 else min_nav * 0.95
            y_top = df_chart['nav'].max() * 1.05

            # Y軸 (主圖)：NAV
            fig.update_yaxes(
                range=[y_bottom, y_top], # 實施 Y 軸壓縮，放大波動視覺
                title_font=dict(color=TEXT_COLOR, size=11),
                tickformat=",.0f", 
                showgrid=True, 
                gridwidth=1, 
                gridcolor=GRID_COLOR,
                showline=True,
                linecolor=GRID_COLOR,
                row=1, col=1
            )
            
            # Y軸 (副圖)：動能槽設定
            fig.update_yaxes(
                showticklabels=False, 
                showgrid=False, 
                zeroline=True, 
                zerolinecolor='#CBD5E1', # 絕對基準線 (淺灰)
                zerolinewidth=1.5, 
                row=2, col=1
            )

            return fig
    return None

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
        <div style="font-size:2.2em; font-weight:bold; color:#00b4d8; line-height:1.1;">
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
