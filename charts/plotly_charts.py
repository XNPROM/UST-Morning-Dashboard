# Source Generated with Decompyle++
# File: plotly_charts.cpython-311.pyc (Python 3.11)

from __future__ import annotations
from plotly.graph_objects import Figure, Scatter, Bar
from config.settings import settings
from analytics.summary import rows_by_section

CHART_COLORS = ['#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed', '#64748b']


def _apply_chart_style(fig, title, ytitle, height=400, bottom_margin=80):
    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor='left', font=dict(family='"IBM Plex Sans", "PingFang SC", "Microsoft YaHei", sans-serif', size=16, color='#0f172a')),
        template=settings.PLOTLY_TEMPLATE,
        colorway=CHART_COLORS,
        hovermode='x unified',
        height=height,
        margin=dict(l=44, r=18, t=56, b=bottom_margin),
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='left', x=0, bgcolor='rgba(255,255,255,0.9)', bordercolor='#e2e8f0', borderwidth=1, font=dict(family='"IBM Plex Sans", "PingFang SC", "Microsoft YaHei", sans-serif', size=11)),
        font=dict(family='"IBM Plex Sans", "PingFang SC", "Microsoft YaHei", sans-serif', size=12, color='#1e293b'),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='#ffffff',
        yaxis_title=ytitle,
        xaxis_title=''
    )
    fig.update_xaxes(showgrid=True, gridcolor='#f1f5f9', linecolor='#e2e8f0', zerolinecolor='#e2e8f0')
    fig.update_yaxes(showgrid=True, gridcolor='#f1f5f9', linecolor='#e2e8f0', zerolinecolor='#e2e8f0')
    return fig


def existing(panel, cols):
    """Return columns that actually exist in the panel."""
    if cols is None:
        return list(panel.columns) if panel is not None else []
    return [c for c in cols if c in panel.columns]


def line_fig(panel, cols=None, title=None, ytitle=None, normalize=False, height=420):
    cols = existing(panel, cols)
    fig = Figure()
    if not cols:
        _apply_chart_style(fig, f'{title}（无可用数据）', ytitle, height)
        return fig
    for col in cols:
        s = panel[col]
        non_null = s.dropna()
        if non_null.empty:
            continue
        if normalize:
            base = float(non_null.iloc[0])
            y = s if base == 0 else (s / base) * 100
        else:
            y = s
        fig.add_trace(Scatter(x=s.index.tz_convert(settings.REPORT_TZ), y=y, mode='lines', name=col, line=dict(width=2), connectgaps=True, hovertemplate='%{x}<br>%{y:.4f}<extra>%{fullData.name}</extra>'))
    return _apply_chart_style(fig, title, ytitle, height)


def change_bar_fig(summary=None, sections=None, title=None):
    df = rows_by_section(summary, sections)
    if df.empty:
        fig = Figure()
        _apply_chart_style(fig, f'{title}（无可用数据）', 'Change', 360, bottom_margin=80)
        return fig
    df = df.copy().dropna(subset=['Change Display'])
    marker_colors = ['#dc2626' if v > 0 else '#16a34a' if v < 0 else '#9ca3af' for v in df['Change Display']]
    fig = Figure(Bar(x=df['Asset'], y=df['Change Display'], text=df['Change Text'], textposition='outside', hovertemplate='%{x}<br>%{y:.4f} %{customdata}<extra></extra>', customdata=df['Change Unit'], marker=dict(color=marker_colors, line=dict(color='#ffffff', width=1))))
    _apply_chart_style(fig, title, 'Change', 380, bottom_margin=88)
    fig.update_xaxes(tickangle=-25)
    fig.add_hline(y=0, line_width=1)
    return fig


def make_figures(main_panel=None, summary_main=None, daily_panel=None, rolling24_panel=None, ny_panel=None):
    figs = []
    # Main window charts
    figs.append(line_fig(main_panel, ['UST 2Y', 'UST 5Y', 'UST 10Y', 'UST 30Y'], '主窗口：美债名义收益率', 'Yield (%)'))
    figs.append(change_bar_fig(summary_main, ['A. Rates', 'B. Real & Inflation'], '主窗口：利率、曲线、BEI变化'))
    figs.append(line_fig(main_panel, ['TIPS real 5Y', 'TIPS real 10Y', 'TIPS real 30Y'], '主窗口：TIPS真实收益率', 'Real yield (%)'))
    figs.append(line_fig(main_panel, ['BEI 5Y', 'BEI 10Y', 'BEI 30Y'], '主窗口：盈亏平衡通胀 BEI', 'BEI (%)'))
    figs.append(line_fig(main_panel, ['TU 2Y Treasury Fut', 'FV 5Y Treasury Fut', 'TY 10Y Treasury Fut', 'US 30Y Treasury Fut'], '主窗口：CBOT美债期货（归一化）', 'Start=100', normalize=True))
    figs.append(line_fig(main_panel, ['DXY'], '主窗口：美元指数 DXY', 'Index'))
    figs.append(line_fig(main_panel, ['EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD'], '主窗口：G10主要汇率（归一化）', 'Start=100', normalize=True))
    figs.append(line_fig(main_panel, ['USDCNY', 'USDCNH'], '主窗口：USDCNY / USDCNH', 'Spot'))
    figs.append(line_fig(daily_panel.tail(260) if daily_panel is not None else None, ['USD/CNY fixing', 'USDCNY', 'USDCNH'], '近一年：人民币中间价 vs CNY/CNH', 'USD/CNY'))
    figs.append(line_fig(main_panel, ['Brent crude', 'WTI crude', 'Gold', 'Copper'], '主窗口：油铜金（归一化）', 'Start=100', normalize=True))
    figs.append(line_fig(daily_panel.tail(260) if daily_panel is not None else None, ['UST 2Y', 'UST 5Y', 'UST 10Y', 'UST 30Y'], '近一年：美债收益率', 'Yield (%)'))
    figs.append(line_fig(daily_panel.tail(260) if daily_panel is not None else None, ['BEI 5Y', 'BEI 10Y', 'BEI 30Y'], '近一年：BEI', 'BEI (%)'))
    # 24h rolling charts
    figs.append(line_fig(rolling24_panel, ['UST 2Y', 'UST 5Y', 'UST 10Y', 'UST 30Y'], '滚动24h：美债收益率', 'Yield (%)'))
    figs.append(line_fig(rolling24_panel, ['DXY'], '滚动24h：美元指数', 'Index'))
    # NY session charts
    figs.append(line_fig(ny_panel, ['UST 2Y'], '纽约时段：UST 2Y', 'Yield (%)'))
    figs.append(line_fig(ny_panel, ['DXY'], '纽约时段：DXY', 'Index'))
    return figs
