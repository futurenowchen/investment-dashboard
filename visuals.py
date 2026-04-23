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
    """繪製戰略級 NAV 趨勢與淨變動複合圖 (Tech Blue Pro Edition)"""
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
            
            # === 科技藍配色設定 (Tech Blue Palette) ===
            BG_COLOR = '#0F172A'          # 沉穩科技藍灰 (Slate 900)
            GRID_COLOR = '#1E293B'        # 低干擾網格線 (Slate 800)
            COLOR_RISE = '#F87171'        # 警示紅 (台股漲)
            COLOR_FALL = '#34D399'        # 薄荷綠 (台股跌)
            COLOR_NAV_MAIN = '#38BDF8'    # 螢光科技青 (Sky 400)
            COLOR_NAV_FILL = 'rgba(56, 189, 248, 0.15)' # 底部微光
            COLOR_SMA = '#94A3B8'         # 戰略灰 (Slate 400)
            TEXT_COLOR = '#CBD5E1'        # 介面冷冽灰 (Slate 300)
            
            colors = [COLOR_RISE if val > 0 else COLOR_FALL for val in df_chart['net_change']]

            # 建立單圖雙 Y 軸複合圖表
            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # 1. 動能柱狀圖 (次座標軸，墊於底層)
            fig.add_trace(
                go.Bar(
                    x=df_chart['dt'],
                    y=df_chart['net_change'],
                    name="Daily Momentum",
                    marker_color=colors,
                    opacity=0.45, # 半透明使其成為背景氛圍
                    marker_line_width=0, 
                    hovertemplate='<span style="font-family: monospace;"><b>DATE:</b> %{x|%Y-%m-%d}<br><b>MOMENTUM:</b> %{y:,.0f}</span><extra></extra>'
                ),
                secondary_y=True,
            )

            # 2. NAV 折線面積圖 (主座標軸，銳利線性 Linear)
            fig.add_trace(
                go.Scatter(
                    x=df_chart['dt'],
                    y=df_chart['nav'],
                    name="Real NAV",
                    fill='tozeroy',
                    mode='lines', 
                    line=dict(
                        color=COLOR_NAV_MAIN, 
                        width=2.5, 
                        shape='linear' # 保持銳利的物理軌跡
                    ),
                    fillcolor=COLOR_NAV_FILL,
                    hovertemplate='<span style="font-family: monospace;"><b>DATE:</b> %{x|%Y-%m-%d}<br><b>NAV :</b> %{y:,.0f}</span><extra></extra>'
                ),
                secondary_y=False,
            )
            
            # 3. 戰略生命線：20日移動平均線 (主座標軸)
            fig.add_trace(
                go.Scatter(
                    x=df_chart['dt'],
                    y=df_chart['SMA20'],
                    name="NAV 20MA",
                    mode='lines',
                    line=dict(color=COLOR_SMA, width=1.5, dash='dash'),
                    hovertemplate='<span style="font-family: monospace;"><b>20MA:</b> %{y:,.0f}</span><extra></extra>'
                ),
                secondary_y=False,
            )

            # 版面優化設定 (Tech Blue Vibe)
            fig.update_layout(
                template='plotly_dark',
                hovermode="x unified",
                margin=dict(t=40, b=20, l=10, r=10),
                plot_bgcolor=BG_COLOR,
                paper_bgcolor=BG_COLOR,
                font=dict(family="Courier New, monospace", size=12, color=TEXT_COLOR),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(color=TEXT_COLOR)
                ),
                hoverlabel=dict(
                    bgcolor="#1E293B",
                    bordercolor=COLOR_NAV_MAIN,
                    font_size=13,
                    font_family="Courier New, monospace",
                    font_color="#ffffff"
                )
            )

            # X軸：消除垂直網格干擾，保留十字準線
            fig.update_xaxes(
                showgrid=False, 
                showspikes=True, 
                spikemode="across",
                spikesnap="cursor",
                spikedash="solid",
                spikethickness=1,
                spikecolor=COLOR_NAV_MAIN, 
                showline=True,
                linecolor=GRID_COLOR,
                showticklabels=True
            )
            
            # Y軸 (主圖)：NAV
            fig.update_yaxes(
                title_text="REAL NAV (TWD)", 
                title_font=dict(color=TEXT_COLOR, size=11),
                secondary_y=False, 
                tickformat=",.0f", 
                showgrid=True, 
                gridwidth=1, 
                gridcolor=GRID_COLOR,
                showline=True,
                linecolor=GRID_COLOR,
            )
            
            # Y軸 (副圖)：動能槽設定
            # 透過放大 Y 軸 Range 來自動壓低柱狀圖的高度，使其不干擾主線
            max_abs_change = df_chart['net_change'].abs().max()
            if pd.notna(max_abs_change) and max_abs_change > 0:
                fig.update_yaxes(
                    range=[-max_abs_change * 3.5, max_abs_change * 3.5], # 壓縮在下方 1/3 處
                    secondary_y=True
                )

            # 隱藏次座標的 Y 軸刻度，僅保留 0 軸絕對基準線
            fig.update_yaxes(
                showticklabels=False, 
                showgrid=False, 
                zeroline=True, 
                zerolinecolor='#334155', # 絕對基準線
                zerolinewidth=1.5, 
                secondary_y=True
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
