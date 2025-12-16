import plotly.express as px
import pandas as pd
import data_manager as dm # 引用格式化工具

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
        background-color: #007bff;
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
        border-left: 5px solid #17a2b8; /* 左側藍色線條 */
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
            fig = px.pie(chart_data, values='num', names='股票')
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            return fig
    return None

def plot_nav_trend(df_F):
    """繪製 NAV 趨勢圖"""
    if not df_F.empty:
        df_calc = df_F.copy()
        if '實質NAV' in df_calc.columns and '日期' in df_calc.columns:
            df_calc['dt'] = pd.to_datetime(df_calc['日期'], errors='coerce')
            df_calc['nav'] = df_calc['實質NAV'].apply(dm.safe_float)
            df_chart = df_calc.sort_values('dt')
            fig = px.line(df_chart, x='dt', y='nav', title='NAV 趨勢', hover_data={'dt': '|%Y-%m-%d', 'nav': ':,.0f'})
            fig.update_traces(hovertemplate='<b>日期</b>: %{x|%Y-%m-%d}<br><b>淨值</b>: %{y:,.0f}<extra></extra>')
            fig.update_layout(hovermode="x unified", yaxis_tickformat=",.0f")
            return fig
    return None

# --- HTML 卡片產生器 (將複雜的 HTML 字串移出 app.py) ---
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
        <div style="font-size:2.2em; font-weight:bold; color:#007bff; line-height:1.1;">
            {pct*100:.1f}%
        </div>
        <div style="margin-top:8px; font-size:0.85em; display:flex; justify-content:space-between; color:#495057;">
            <span>目標: <b>{dm.fmt_int(target)}</b></span>
        </div>
          <div style="text-align:right; font-size:0.8em; color:#dc3545; margin-top:2px;">
            (差 {dm.fmt_int(gap)})
        </div>
    </div>
    """

def render_house_plan_card(r_display, dp_target, est_year):
    return f"""
    <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; margin-bottom:10px; border:1px solid #e9ecef; height: 100%; display: flex; flex-direction: column; justify-content: center;">
        <div style="font-size:1.0em; color:#6c757d; margin-bottom:5px;">房屋準備度 R</div>
        <div style="font-size:2.2em; font-weight:bold; color:#007bff; line-height:1.1;">
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
