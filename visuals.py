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
    .block-container {
        padding-top: 5rem;
        padding-bottom: 2rem;
    }

    html, body, [class*="stApp"] { font-size: 16px; }
    h1 { font-size: 2.2em; margin-bottom: 0.5rem; }
    h2 { font-size: 1.6em; padding-top: 0.5rem; }
    h3 { font-size: 1.4em; }

    [data-testid="stDataFrame"] thead {
        display: none;
    }

    div[data-testid="stSidebar"] .stButton button {
        width: 100%;
        height: 45px;
        margin-bottom: 10px;
        border: 1px solid #ccc;
    }

    .stProgress > div > div > div > div {
        background-color: #00b4d8;
    }

    .custom-metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 12px;
        text-align: center;
        height: 100%;
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
        font-size: 2.0em;
        font-weight: bold;
        color: #212529;
        line-height: 1.1;
    }

    .metric-badge {
        display: block;
        width: 100%;
        padding: 6px 0;
        border-radius: 6px;
        color: white;
        font-size: 1.1em;
        font-weight: bold;
        margin-bottom: 10px;
    }

    .mindset-card {
        background-color: #e8f4f8;
        border-left: 5px solid #00b4d8;
        padding: 14px 16px;
        border-radius: 5px;
        margin-top: 12px;
        color: #0f5132;
        font-size: 1.0em;
        display: flex;
        align-items: center;
        min-height: 64px;
        width: 100%;
        line-height: 1.35;
        overflow-wrap: anywhere;
        word-break: break-word;
        transition: background-color 0.35s ease, box-shadow 0.35s ease, border-color 0.35s ease;
        animation: cardFadeIn 0.35s ease-out;
    }

    .live-card {
        background-color:#f8f9fa;
        padding:14px 16px;
        border-radius:10px;
        margin-bottom:10px;
        border:1px solid #e9ecef;
        min-height:118px;
        display:flex;
        flex-direction:column;
        justify-content:center;
        align-items:center;
        text-align:center;
        line-height:1.2;
        overflow:hidden;
        transition: background-color 0.3s ease, box-shadow 0.3s ease, transform 0.25s ease;
        animation: cardFadeIn 0.3s ease-out;
    }

    .live-card-label {
        min-height: 24px;
        font-size:1em;
        color:#6c757d;
        line-height:1.25;
        margin-bottom:4px;
        overflow-wrap:anywhere;
        word-break:break-word;
    }

    .live-card-value {
        min-height: 48px;
        font-size:2.2em;
        font-weight:700;
        line-height:1.1;
        display:flex;
        align-items:center;
        justify-content:center;
        overflow-wrap:anywhere;
        word-break:break-word;
    }

    .mini-metric-card {
        min-height: 92px;
        padding: 4px 0;
        display:flex;
        flex-direction:column;
        justify-content:center;
        transition: color 0.3s ease;
        animation: cardFadeIn 0.3s ease-out;
    }

    .mini-metric-label {
        min-height: 24px;
        font-size:1.05rem;
        color:gray;
        margin-bottom:2px;
        line-height:1.2;
        overflow-wrap:anywhere;
    }

    .mini-metric-value {
        min-height: 54px;
        font-size:1.75rem;
        font-weight:700;
        line-height:1.15;
        display:flex;
        flex-direction:column;
        justify-content:center;
        overflow-wrap:anywhere;
        word-break:break-word;
    }

    .live-highlight {
        box-shadow: 0 0 0 1px rgba(0, 180, 216, 0.18), 0 8px 16px rgba(15, 23, 42, 0.05);
    }

    @keyframes cardFadeIn {
        from { opacity: 0.88; }
        to { opacity: 1; }
    }
    </style>
    """


# --- 圖表繪製 ---
def plot_asset_allocation(df_B):
    """繪製資產配置圓餅圖"""
    if not df_B.empty and '市值（元）' in df_B.columns:
        df_B = df_B.copy()
        df_B['num'] = df_B['市值（元）'].apply(dm.safe_float)

        chart_data = df_B[
            (df_B['num'] > 0)
            & (~df_B['股票'].astype(str).str.contains('總資產|Total', na=False))
        ]

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
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.2,
                    xanchor="center",
                    x=0.5
                )
            )

            return fig

    return None


def plot_nav_trend(df_F):
    """繪製戰略級 NAV 趨勢與淨變動複合圖"""
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

            bg_color = '#FFFFFF'
            grid_color = '#F1F5F9'
            color_rise = '#FF0000'
            color_fall = '#009900'
            color_nav_main = '#00B4D8'
            color_nav_fill = 'rgba(0, 180, 216, 0.08)'
            color_sma = '#94A3B8'
            text_color = '#334155'
            modern_font = "Arial, 'Heiti TC', 'Microsoft JhengHei', sans-serif"

            colors = [color_rise if val > 0 else color_fall for val in df_chart['net_change']]
            df_chart['hover_color'] = colors

            fig = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.75, 0.25]
            )

            fig.add_trace(
                go.Scatter(
                    x=df_chart['dt'],
                    y=df_chart['nav'],
                    name="每日淨值",
                    fill='tozeroy',
                    mode='lines',
                    line=dict(color=color_nav_main, width=2.5, shape='spline', smoothing=0.8),
                    fillcolor=color_nav_fill,
                    customdata=df_chart[['net_change', 'SMA20', 'hover_color']].values,
                    hovertemplate=(
                        '<b>日期：%{x|%Y-%m-%d}</b><br><br>'
                        '<b>每日淨值：</b> %{y:,.0f}<br>'
                        '<b>淨值變化：</b> '
                        '<span style="color:%{customdata[2]}">%{customdata[0]:+,.0f}</span><br>'
                        '<b>NAV 20MA：</b> %{customdata[1]:,.0f}'
                        '<extra></extra>'
                    )
                ),
                row=1,
                col=1
            )

            fig.add_trace(
                go.Scatter(
                    x=df_chart['dt'],
                    y=df_chart['SMA20'],
                    name="NAV 20MA",
                    mode='lines',
                    line=dict(color=color_sma, width=1.5, dash='dash'),
                    hoverinfo='skip'
                ),
                row=1,
                col=1
            )

            fig.add_trace(
                go.Bar(
                    x=df_chart['dt'],
                    y=df_chart['net_change'],
                    name="淨值變化",
                    marker_color=colors,
                    opacity=0.75,
                    marker_line_width=0,
                    hoverinfo='skip'
                ),
                row=2,
                col=1
            )

            fig.update_layout(
                template='plotly_white',
                hovermode="x",
                margin=dict(t=40, b=10, l=10, r=10),
                plot_bgcolor=bg_color,
                paper_bgcolor=bg_color,
                font=dict(family=modern_font, size=13, color=text_color),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    font=dict(family=modern_font, color=text_color)
                ),
                hoverlabel=dict(
                    bgcolor="#FFFFFF",
                    bordercolor=color_nav_main,
                    font_size=14,
                    font_family=modern_font,
                    font_color="#334155"
                )
            )

            fig.update_xaxes(
                showgrid=False,
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
                spikedash="solid",
                spikethickness=1,
                spikecolor="#CBD5E1",
                showline=True,
                linecolor=grid_color,
                row=1,
                col=1
            )

            fig.update_xaxes(
                showgrid=False,
                showline=True,
                linecolor=grid_color,
                row=2,
                col=1
            )

            min_nav = df_chart['nav'].min()
            max_nav = df_chart['nav'].max()
            y_bottom = 1400000 if min_nav > 1400000 else min_nav * 0.95
            y_top = max_nav * 1.05

            if max_nav < 5000000:
                nav_dtick = 200000
            elif max_nav < 10000000:
                nav_dtick = 300000
            else:
                nav_dtick = 500000

            fig.update_yaxes(
                range=[y_bottom, y_top],
                title_font=dict(family=modern_font, color=text_color, size=12),
                tickformat=",.0f",
                dtick=nav_dtick,
                showgrid=True,
                gridwidth=1,
                gridcolor=grid_color,
                showline=True,
                linecolor=grid_color,
                row=1,
                col=1
            )

            fig.update_yaxes(
                showticklabels=False,
                showgrid=False,
                zeroline=True,
                zerolinecolor='#CBD5E1',
                zerolinewidth=1.5,
                row=2,
                col=1
            )

            return fig

    return None


def plot_wealth_trajectory(df_F=None):
    """繪製 NEGENTROPIC ATARAXIA 財富路徑導航圖"""

    def frac_year_to_quarter_label(x):
        q_index = int(np.round((float(x) - 2025.0) * 4))
        y = 2025.0 + q_index / 4.0
        year = int(np.floor(y))
        frac = y - year
        quarter = int(np.round(frac * 4)) + 1
        quarter = min(max(quarter, 1), 4)
        return f"{year} Q{quarter}"

    anchor_offset = 113 / 365.25
    years = [2026, 2027, 2028, 2029, 2030, 2033, 2035, 2036, 2038, 2039, 2040]
    theoretical_x = [2025.67, 2026.0] + [y + anchor_offset for y in years]

    nav_8 = [1.47, 2.058] + [2.9, 3.3, 4.6, 5.1, 6.4, 8.6, 10.3, 11.3, 13.4, 14.7, 16.0]
    nav_15 = [1.47, 2.058] + [2.9, 3.9, 4.8, 5.7, 6.6, 10.2, 13.7, 15.7, 19.0, 21.7, 24.2]
    nav_175 = [1.47, 2.058] + [2.9, 4.6, 5.5, 7.0, 8.1, 13.0, 17.5, 20.0, 30.0, 33.8, 36.2]
    nav_20 = [1.47, 2.058] + [2.9, 5.1, 6.8, 8.6, 10.5, 18.6, 27.1, 37.0, 57.0, 63.6, 68.7]

    modern_font = "Arial, 'Heiti TC', 'Microsoft JhengHei', sans-serif"
    fig = go.Figure()

    # 淡化戰略區域底色
    phase_blocks = [
        (2026.0, 2027.5, '#DBEAFE', 'Phase 1｜窒息期 2026–2027'),
        (2027.5, 2028.5, '#DCFCE7', 'Phase 2｜注資期 2027.5–2028.5'),
        (2028.5, 2030.0, '#FEF3C7', 'Phase 3｜加速期 2028.5–2030'),
        (2030.0, 2034.0, '#EDE9FE', 'Phase 4｜隱形加速 2030–2034'),
        (2034.0, 2040.0, '#FEE2E2', 'Phase 5｜自由區域 2034–2040'),
    ]
    for x0, x1, c, t in phase_blocks:
        fig.add_shape(type='rect', x0=x0, x1=x1, y0=0, y1=1, yref='paper', line_width=0,
                      fillcolor=c, opacity=0.15, layer='below')
        fig.add_annotation(x=(x0 + x1) / 2, y=0.965, yref='paper', text=t, showarrow=False,
                           font=dict(size=12, color='#64748B', family=modern_font))

    # 五條核心路徑
    fig.add_trace(go.Scatter(x=theoretical_x, y=nav_20, name='🔴 野心上限', mode='lines',
                             line=dict(color='#DC2626', width=2.6), line_shape='spline', hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=theoretical_x, y=nav_175, name='🟢 基準目標', mode='lines',
                             line=dict(color='#166534', width=3.0), line_shape='spline', hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=theoretical_x, y=nav_15, name='🔵 保守路徑', mode='lines',
                             line=dict(color='#1D4ED8', width=2.4), line_shape='spline', hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=theoretical_x, y=nav_8, name='🛡️ 大盤防線', mode='lines',
                             line=dict(color='#94A3B8', width=2.0, dash='dash'), line_shape='spline', hoverinfo='skip'))

    # 實際戰線
    has_real = False
    df_real = pd.DataFrame()
    if df_F is not None and not df_F.empty:
        df_real = df_F.copy()
        date_col = next((c for c in df_real.columns if '日期' in c), None)
        if date_col and '實質NAV' in df_real.columns:
            df_real['dt'] = pd.to_datetime(df_real[date_col], errors='coerce')
            df_real['nav_raw'] = df_real['實質NAV'].apply(dm.safe_float)
            df_real = df_real.dropna(subset=['dt'])
            df_real = df_real[df_real['nav_raw'] > 0]
            if not df_real.empty:
                has_real = True
                df_real = df_real.sort_values('dt')
                df_real['frac_year'] = df_real['dt'].dt.year + (df_real['dt'].dt.dayofyear - 1) / 365.25
                df_real['nav_m'] = df_real['nav_raw'] / 1000000.0
                df_real['date_str'] = df_real['dt'].dt.strftime('%Y-%m-%d')

                fig.add_trace(go.Scatter(
                    x=df_real['frac_year'], y=df_real['nav_m'], name='⚡ 實際戰線光暈',
                    mode='lines', line=dict(color='rgba(245, 158, 11, 0.20)', width=9),
                    line_shape='spline', hoverinfo='skip', showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=df_real['frac_year'], y=df_real['nav_m'], name='⚡ 實際戰線',
                    mode='lines', line=dict(color='#F59E0B', width=4),
                    line_shape='spline', hoverinfo='skip'
                ))

                last_x = df_real['frac_year'].iloc[-1]
                last_y = df_real['nav_m'].iloc[-1]
                fig.add_trace(go.Scatter(x=[last_x], y=[last_y], name='最新定位點', mode='markers+text',
                                         text=[f'⚡ {last_y:.2f}M'], textposition='top left',
                                         marker=dict(size=13, symbol='circle', color='#F59E0B',
                                                     line=dict(color='white', width=2)),
                                         textfont=dict(size=12, color='#B45309', family=modern_font),
                                         hoverinfo='skip', showlegend=False))

    # 事件線統一
    events = [
        (2027 + anchor_offset, '2027/05 車貸結束'),
        (2027.75, '2027 Q4 注資'),
        (2029.75, '2029 Q4 注資'),
        (2030.0, '2030 千萬檢查點'),
    ]
    for x, label in events:
        fig.add_vline(x=x, line_width=1, line_dash='dot', line_color='rgba(100,116,139,0.50)', layer='below')
        fig.add_annotation(x=x, y=0.93, yref='paper', text=label, showarrow=False,
                           font=dict(size=12, color='#475569', family=modern_font),
                           bgcolor='rgba(255,255,255,0.75)', bordercolor='rgba(148,163,184,0.35)', borderwidth=1)

    # 里程碑改為水平參考線
    for lvl, label in [(3, '3M｜穩態防守線'), (5, '5M｜臨界門檻'), (10, '10M｜千萬射程'), (35, '35M｜自由區')]:
        fig.add_hline(y=lvl, line_width=1, line_dash='dash', line_color='rgba(148,163,184,0.45)', layer='below')
        fig.add_annotation(x=2040.35, y=lvl, text=label, xanchor='left', showarrow=False,
                           font=dict(size=12, color='#64748B', family=modern_font),
                           bgcolor='rgba(255,255,255,0.68)')

    # 稀疏理論關鍵節點標註
    key_years = {2026, 2027, 2030, 2035, 2040}
    for x, y in zip(theoretical_x, nav_175):
        if int(np.floor(x)) in key_years:
            fig.add_annotation(x=x, y=y, text=frac_year_to_quarter_label(x), showarrow=False,
                               yshift=16, font=dict(size=12, color='#166534', family=modern_font))

    # hover 雷達
    start_q = 2025.5   # 2025 Q3
    end_q = 2040.75    # 2040 Q4
    hover_x = np.arange(start_q, end_q + 0.001, 1 / 52)
    hover_x = np.round(hover_x, 6)
    hover_df = pd.DataFrame({'frac_year': hover_x})
    hover_df['exp_20'] = np.interp(hover_df['frac_year'], theoretical_x, nav_20)
    hover_df['exp_175'] = np.interp(hover_df['frac_year'], theoretical_x, nav_175)
    hover_df['exp_15'] = np.interp(hover_df['frac_year'], theoretical_x, nav_15)
    hover_df['exp_8'] = np.interp(hover_df['frac_year'], theoretical_x, nav_8)

    if has_real:
        real_x = df_real['frac_year'].values
        real_y = df_real['nav_m'].values
        hover_df['real_nav'] = np.where((hover_df['frac_year'] >= real_x.min()) & (hover_df['frac_year'] <= real_x.max()),
                                        np.interp(hover_df['frac_year'], real_x, real_y), np.nan)
        real_dates_x = df_real['frac_year'].values
        real_dates_label = df_real['date_str'].values
        date_match_threshold = 10 / 365.25  # 約 10 天內顯示實際日期

        def resolve_hover_label(x):
            idx = np.abs(real_dates_x - x).argmin()
            if abs(real_dates_x[idx] - x) <= date_match_threshold:
                return real_dates_label[idx]
            return frac_year_to_quarter_label(x)

        hover_df['date_label'] = hover_df['frac_year'].apply(resolve_hover_label)
    else:
        hover_df['real_nav'] = np.nan
        hover_df['date_label'] = hover_df['frac_year'].apply(frac_year_to_quarter_label)

    hover_df['real_text'] = hover_df['real_nav'].apply(lambda v: f'{v:.2f}M' if pd.notna(v) else '—')
    hover_customdata = hover_df[['date_label', 'real_text', 'exp_20', 'exp_175', 'exp_15', 'exp_8']].values
    fig.add_trace(go.Scatter(
        x=hover_df['frac_year'],
        y=hover_df['exp_175'],
        name='📌 戰略座標雷達',
        mode='lines',
        line=dict(color='rgba(0,0,0,0.01)', width=26),
        customdata=hover_customdata,
        showlegend=False,
        hovertemplate=(
            '<b>📌 戰略座標｜%{customdata[0]}</b><br><br>'
            '⚡ 實際戰線：<b>%{customdata[1]}</b><br>'
            '🔴 野心上限：%{customdata[2]:.2f}M<br>'
            '🟢 基準目標：%{customdata[3]:.2f}M<br>'
            '🔵 保守路徑：%{customdata[4]:.2f}M<br>'
            '🛡️ 大盤防線：%{customdata[5]:.2f}M'
            '<extra></extra>'
        )
    ))

    # 半年刻度標籤
    tickvals = np.arange(2025.5, 2040.6, 0.5)
    ticktext = [frac_year_to_quarter_label(x) for x in tickvals]

    fig.update_layout(
        title=dict(
            text=("<b>NEGENTROPIC ATARAXIA 個人資產戰略航線圖</b><br>"
                  "<span style='font-size:14px; color:#64748B;'>"
                  "主視角：2026–2030｜路徑：300 → 500 → 1000 → 自由區"
                  "</span>"),
            font=dict(size=20, family=modern_font), x=0.5, xanchor='center', y=0.98, yanchor='top'
        ),
        template='plotly_white',
        hovermode='x unified',
        margin=dict(t=170, b=125, l=70, r=70),
        font=dict(family=modern_font, color='#334155', size=13),
        legend=dict(orientation='h', yanchor='bottom', y=1.03, xanchor='center', x=0.5,
                    font=dict(size=15), bgcolor='rgba(255,255,255,0.9)', bordercolor='#E2E8F0', borderwidth=1),
        hoverlabel=dict(bgcolor='#FFFFFF', bordercolor='#CBD5E1', font_size=15, font_family=modern_font,
                        font_color='#334155', align='left'),
        updatemenus=[dict(type='dropdown', direction='down', x=0.0, y=1.13, xanchor='left', yanchor='bottom',
                          showactive=True, active=0, bgcolor='#FFFFFF', bordercolor='#CBD5E1',
                          font=dict(family=modern_font, color='#334155', size=14),
                          buttons=[
                              dict(label='🎯 主戰區 2026–2030', method='relayout', args=[{'xaxis.range':[2025.75,2030.5],'yaxis.range':[1,12]}]),
                              dict(label='🛡️ 窒息期 2026–2027', method='relayout', args=[{'xaxis.range':[2025.75,2027.6],'yaxis.range':[1,6]}]),
                              dict(label='🚀 加速期 2028–2030', method='relayout', args=[{'xaxis.range':[2027.5,2030.5],'yaxis.range':[3,15]}]),
                              dict(label='🏔️ 自由區 2030–2040', method='relayout', args=[{'xaxis.range':[2030,2040.5],'yaxis.range':[8,75]}]),
                              dict(label='🗺️ 全景 2025–2040', method='relayout', args=[{'xaxis.range':[2024.5,2040.5],'yaxis.range':[0,75]}]),
                          ])],
        plot_bgcolor='#FFFFFF', paper_bgcolor='#FFFFFF', xaxis_title='', yaxis_title='總資產 NAV (百萬 TWD)', height=980
    )

    fig.update_xaxes(showgrid=True, gridcolor='#F1F5F9', tickvals=tickvals, ticktext=ticktext,
                     tickfont=dict(size=12), showline=True, linecolor='#CBD5E1', range=[2025.75, 2030.5])
    fig.update_yaxes(showgrid=True, gridcolor='#F1F5F9', showline=True, linecolor='#CBD5E1', zeroline=False,
                     range=[1, 12], dtick=1, tickfont=dict(size=13), title_font=dict(size=14))

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
    <div class="live-card live-highlight">
        <div class="live-card-label">達成進度</div>
        <div class="live-card-value" style="color:#007BFF;">
            {pct*100:.1f}%
        </div>
        <div style="margin-top:8px; min-height:20px; font-size:0.85em; display:flex; justify-content:space-between; color:#495057; line-height:1.25; width:100%;">
            <span>目標: <b>{dm.fmt_int(target)}</b></span>
        </div>
        <div style="min-height:18px; text-align:right; font-size:0.8em; color:#e63946; margin-top:2px; line-height:1.2; width:100%;">
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
    <div class="live-card live-highlight">
        <div class="live-card-label">{title}</div>
        <div class="live-card-value" style="color:{value_color};">
            {value}
        </div>
    </div>
    """


def render_mindset_card(mindset_text):
    return f"""
    <div class="mindset-card">
        <div style="line-height:1.35;">💡 <b>心態提醒：</b> {mindset_text}</div>
    </div>
    """


def render_mini_metric(label, value, color="black"):
    return f"""
    <div class='mini-metric-card'>
        <div class='mini-metric-label'>{label}</div>
        <div class='mini-metric-value' style='color:{color};'>{value}</div>
    </div>
    """
