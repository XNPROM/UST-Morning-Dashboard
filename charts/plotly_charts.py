from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from plotly.graph_objects import Figure, Scatter, Bar
from config.settings import settings
from analytics.summary import rows_by_section, lookup, _last_complete_rows

CHART_COLORS = ['#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed', '#64748b']

DECOMP_COLORS = {'nominal': '#2563eb', 'real': '#7c3aed', 'bei': '#d97706'}

SECTION_META = {
    'rates': '1. Rates & Curve',
    'futures': '2. Treasury Futures',
    'fx': '3. FX & RMB',
    'commodities': '4. Commodities',
    'longterm': '5. Long-term Context',
}

NY_TZ = ZoneInfo('America/New_York')

UTC = ZoneInfo('UTC')


@dataclass
class ChartSpec:
    fig: Figure
    section: str
    width: str
    priority: int


def _ny_session_times(asof_dt):
    """Return NY open/close as UTC datetimes for the most recent trading day."""
    ny_date = asof_dt.astimezone(NY_TZ).date()
    # Try today first, then yesterday if market hasn't opened yet
    for offset in (0, 1):
        d = ny_date - pd.Timedelta(days=offset)
        try:
            open_utc = datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY_TZ).astimezone(UTC)
            close_utc = datetime(d.year, d.month, d.day, 16, 0, tzinfo=NY_TZ).astimezone(UTC)
            if open_utc <= asof_dt.astimezone(UTC):
                return open_utc, close_utc
        except Exception:
            continue
    return None, None


def _add_session_lines(fig, panel, asof_dt=None):
    """Add vertical lines for NY open/close on intraday charts."""
    if panel is None or panel.empty or asof_dt is None:
        return fig
    open_utc, close_utc = _ny_session_times(asof_dt)
    if open_utc and close_utc:
        open_str = open_utc.strftime('%Y-%m-%d %H:%M:%S')
        close_str = close_utc.strftime('%Y-%m-%d %H:%M:%S')
        data_start = panel.index.min().tz_convert(UTC).tz_localize(None)
        data_end = panel.index.max().tz_convert(UTC).tz_localize(None)
        open_naive = open_utc.replace(tzinfo=None)
        close_naive = close_utc.replace(tzinfo=None)
        if data_start <= open_naive <= data_end:
            fig.add_shape(type='line', x0=open_str, x1=open_str, y0=0, y1=1, yref='paper',
                          line=dict(dash='dot', color='#94a3b8', width=1))
            fig.add_annotation(x=open_str, y=1, yref='paper', text='NY open',
                               showarrow=False, font=dict(size=10, color='#94a3b8'),
                               xanchor='left', yanchor='bottom')
        if data_start <= close_naive <= data_end:
            fig.add_shape(type='line', x0=close_str, x1=close_str, y0=0, y1=1, yref='paper',
                          line=dict(dash='dot', color='#94a3b8', width=1))
            fig.add_annotation(x=close_str, y=1, yref='paper', text='NY close',
                               showarrow=False, font=dict(size=10, color='#94a3b8'),
                               xanchor='left', yanchor='bottom')
    return fig


def _apply_chart_style(fig, title, ytitle, height=380, bottom_margin=72, width_hint='full'):
    if width_hint == 'half':
        title_size = 14
        margin = dict(l=36, r=12, t=48, b=bottom_margin)
    else:
        title_size = 16
        margin = dict(l=44, r=18, t=56, b=bottom_margin)
    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor='left', font=dict(family='"IBM Plex Sans", "PingFang SC", "Microsoft YaHei", sans-serif', size=title_size, color='#0f172a')),
        template=settings.PLOTLY_TEMPLATE,
        colorway=CHART_COLORS,
        hovermode='x unified',
        height=height,
        margin=margin,
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='left', x=0, bgcolor='rgba(255,255,255,0.9)', bordercolor='#e2e8f0', borderwidth=1, font=dict(family='"IBM Plex Sans", "PingFang SC", "Microsoft YaHei", sans-serif', size=11)),
        font=dict(family='"IBM Plex Sans", "PingFang SC", "Microsoft YaHei", sans-serif', size=12, color='#1e293b'),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='#fafbfc',
        yaxis_title=ytitle,
        xaxis_title='',
        autosize=True,
    )
    fig.update_xaxes(showgrid=True, gridcolor='#eef2f6', linecolor='#e2e8f0', zerolinecolor='#e2e8f0')
    fig.update_yaxes(showgrid=True, gridcolor='#eef2f6', linecolor='#e2e8f0', zerolinecolor='#e2e8f0')
    return fig


def existing(panel, cols):
    if cols is None:
        return list(panel.columns) if panel is not None else []
    return [c for c in cols if c in panel.columns]


def line_fig(panel, cols=None, title=None, ytitle=None, normalize=False, height=380, width_hint='full', asof_dt=None):
    cols = existing(panel, cols)
    fig = Figure()
    if not cols:
        return None
    added = 0
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
        fig.add_trace(Scatter(x=s.index.tz_convert(UTC).tz_localize(None), y=y, mode='lines', name=col, line=dict(width=2), connectgaps=True, hovertemplate='%{x}<br>%{y:.4f}<extra>%{fullData.name}</extra>'))
        added += 1
    if added == 0:
        return None
    _apply_chart_style(fig, title, ytitle, height, width_hint=width_hint)
    if asof_dt:
        _add_session_lines(fig, panel, asof_dt)
    return fig


def area_fig(panel, cols=None, title=None, ytitle=None, height=340, width_hint='half', asof_dt=None):
    cols = existing(panel, cols)
    fig = Figure()
    if not cols:
        return None
    added = 0
    for col in cols:
        s = panel[col]
        non_null = s.dropna()
        if non_null.empty:
            continue
        fig.add_trace(Scatter(x=s.index.tz_convert(UTC).tz_localize(None), y=s, mode='lines', name=col, line=dict(width=1.5), fill='tozeroy', connectgaps=True, hovertemplate='%{x}<br>%{y:.4f}<extra>%{fullData.name}</extra>'))
        added += 1
    if added == 0:
        return None
    _apply_chart_style(fig, title, ytitle, height, width_hint=width_hint)
    if asof_dt:
        _add_session_lines(fig, panel, asof_dt)
    return fig


def yield_curve_overlay_fig(daily_panel):
    idx = _last_complete_rows(daily_panel, 2)
    if len(idx) < 2:
        return None
    prev_row = daily_panel.iloc[idx[1]]
    curr_row = daily_panel.iloc[idx[0]]
    tenors = ['UST 2Y', 'UST 5Y', 'UST 10Y', 'UST 30Y']
    labels = ['2Y', '5Y', '10Y', '30Y']
    prev_vals = [float(prev_row[t]) for t in tenors if t in daily_panel.columns and pd.notna(prev_row.get(t))]
    curr_vals = [float(curr_row[t]) for t in tenors if t in daily_panel.columns and pd.notna(curr_row.get(t))]
    tenor_labels = [l for t, l in zip(tenors, labels) if t in daily_panel.columns and pd.notna(prev_row.get(t)) and pd.notna(curr_row.get(t))]
    if len(tenor_labels) < 2:
        return None
    fig = Figure()
    fig.add_trace(Scatter(x=tenor_labels, y=prev_vals, mode='lines+markers', name='Previous close', line=dict(width=2, dash='dash', color='#94a3b8'), marker=dict(size=8)))
    fig.add_trace(Scatter(x=tenor_labels, y=curr_vals, mode='lines+markers', name='Current close', line=dict(width=2.5, color='#2563eb'), marker=dict(size=8)))
    _apply_chart_style(fig, 'Yield Curve: Prev vs Current Close', 'Yield (%)', 340, width_hint='half')
    fig.update_yaxes(tickformat='.2f')
    fig.update_xaxes(type='category')
    return fig


def rate_decomposition_fig(summary_daily, summary_24h=None):
    if summary_daily is None or summary_daily.empty:
        return None
    tenors = ['5Y', '10Y', '30Y']
    nom_names = [f'UST {t}' for t in tenors]
    real_names = [f'TIPS real {t}' for t in tenors]
    bei_names = [f'BEI {t}' for t in tenors]
    nom_vals, real_vals, bei_vals, labels = [], [], [], []
    for nom, real, bei, label in zip(nom_names, real_names, bei_names, tenors):
        nr = lookup(summary_daily, nom)
        if nr is None:
            continue
        rr = lookup(summary_daily, real)
        br = lookup(summary_daily, bei)
        if (rr is None or br is None) and summary_24h is not None:
            rr = rr or lookup(summary_24h, real)
            br = br or lookup(summary_24h, bei)
        nom_vals.append(float(nr['Change Display']))
        real_vals.append(float(rr['Change Display']) if rr is not None else None)
        bei_vals.append(float(br['Change Display']) if br is not None else None)
        labels.append(label)
    if not labels:
        return None
    has_real = any(v is not None for v in real_vals)
    has_bei = any(v is not None for v in bei_vals)
    if not has_real and not has_bei:
        return None
    fig = Figure()
    real_vals_plot = [v if v is not None else 0 for v in real_vals]
    bei_vals_plot = [v if v is not None else 0 for v in bei_vals]
    fig.add_trace(Bar(x=labels, y=nom_vals, name='Nominal', marker_color=DECOMP_COLORS['nominal']))
    fig.add_trace(Bar(x=labels, y=real_vals_plot, name='Real yield' + (' (24h)' if has_real and any(lookup(summary_daily, r) is None for r in real_names) else ''), marker_color=DECOMP_COLORS['real']))
    fig.add_trace(Bar(x=labels, y=bei_vals_plot, name='BEI' + (' (24h)' if has_bei and any(lookup(summary_daily, b) is None for b in bei_names) else ''), marker_color=DECOMP_COLORS['bei']))
    _apply_chart_style(fig, 'Rate Decomposition (close-to-close, bp)', 'Change (bp)', 340, width_hint='half')
    fig.update_layout(barmode='group', bargap=0.25, bargroupgap=0.1)
    fig.add_hline(y=0, line_width=1, line_color='#94a3b8')
    return fig


def section_change_bar_fig(summary=None, sections=None, title=None, ytitle=None, width_hint='half'):
    df = rows_by_section(summary, sections)
    if df.empty:
        return None
    df = df.copy().dropna(subset=['Change Display'])
    marker_colors = ['#dc2626' if v > 0 else '#16a34a' if v < 0 else '#9ca3af' for v in df['Change Display']]
    fig = Figure(Bar(x=df['Asset'], y=df['Change Display'], text=df['Change Text'], textposition='outside', hovertemplate='%{x}<br>%{y:.4f} %{customdata}<extra></extra>', customdata=df['Change Unit'], marker=dict(color=marker_colors, line=dict(color='#ffffff', width=1))))
    _apply_chart_style(fig, title, ytitle, 340, bottom_margin=72, width_hint=width_hint)
    fig.update_xaxes(tickangle=-25)
    fig.add_hline(y=0, line_width=1, line_color='#94a3b8')
    return fig


def dual_axis_line_fig(panel, cols_left=None, cols_right=None, title=None, ytitle_left=None, ytitle_right=None, height=340, width_hint='half'):
    cols_l = existing(panel, cols_left)
    cols_r = existing(panel, cols_right)
    fig = Figure()
    if not cols_l and not cols_r:
        return None
    added = 0
    for col in cols_l:
        s = panel[col].dropna()
        if s.empty:
            continue
        fig.add_trace(Scatter(x=s.index.tz_convert(UTC).tz_localize(None), y=s, mode='lines', name=col, line=dict(width=2), connectgaps=True, hovertemplate='%{x}<br>%{y:.4f}<extra>%{fullData.name}</extra>'))
        added += 1
    for col in cols_r:
        s = panel[col].dropna()
        if s.empty:
            continue
        fig.add_trace(Scatter(x=s.index.tz_convert(UTC).tz_localize(None), y=s, mode='lines', name=col, line=dict(width=2, dash='dot'), connectgaps=True, yaxis='y2', hovertemplate='%{x}<br>%{y:.4f}<extra>%{fullData.name}</extra>'))
        added += 1
    if added == 0:
        return None
    layout_extra = {}
    if cols_r:
        layout_extra['yaxis2'] = dict(overlaying='y', side='right', title=ytitle_right or '', showgrid=False, linecolor='#e2e8f0', zerolinecolor='#e2e8f0')
    _apply_chart_style(fig, title, ytitle_left or '', height, width_hint=width_hint)
    if layout_extra:
        fig.update_layout(**layout_extra)
    return fig



def make_figures(summary_daily=None, summary_24h=None, daily_panel=None, rolling24_panel=None, asof_dt=None):
    figs = []

    # --- Section: rates ---
    # 1. UST yields session
    fig = line_fig(rolling24_panel, ['UST 2Y', 'UST 5Y', 'UST 10Y', 'UST 30Y'], 'UST Yields', 'Yield (%)', height=380, width_hint='full', asof_dt=asof_dt)
    if fig:
        figs.append(ChartSpec(fig, 'rates', 'full', 10))

    # 2. Rate decomposition
    fig = rate_decomposition_fig(summary_daily, summary_24h)
    if fig:
        figs.append(ChartSpec(fig, 'rates', 'half', 20))

    # 3. Yield curve overlay
    fig = yield_curve_overlay_fig(daily_panel)
    if fig:
        figs.append(ChartSpec(fig, 'rates', 'half', 30))

    # 4. Curve spreads 1Y
    d1y = daily_panel.tail(260) if daily_panel is not None else None
    fig = line_fig(d1y, ['UST 2s10s spread', 'UST 5s30s spread'], 'Curve Spreads (1Y)', 'bp', height=340, width_hint='full')
    if fig:
        figs.append(ChartSpec(fig, 'rates', 'full', 40))

    # 5. BEI 1Y daily close
    fig = line_fig(d1y, ['BEI 5Y', 'BEI 10Y', 'BEI 30Y'], 'BEI Inflation Expectation (1Y daily)', 'BEI (%)', height=340, width_hint='half')
    if fig:
        figs.append(ChartSpec(fig, 'rates', 'half', 50))

    # 6. Rate decomposition bar stays as half, add a half chart for TIPS/real context
    # Replace TIPS 24h with BEI session (intraday)
    fig = area_fig(rolling24_panel, ['BEI 5Y', 'BEI 10Y', 'BEI 30Y'], 'BEI Intraday', 'BEI (%)', asof_dt=asof_dt)
    if fig:
        figs.append(ChartSpec(fig, 'rates', 'half', 60))

    # --- Section: futures ---
    # 7. Treasury futures session
    fig = line_fig(rolling24_panel, ['TU 2Y Treasury Fut', 'FV 5Y Treasury Fut', 'TY 10Y Treasury Fut', 'US 30Y Treasury Fut'], 'Treasury Futures (normalized)', 'Start=100', normalize=True, height=380, width_hint='full', asof_dt=asof_dt)
    if fig:
        figs.append(ChartSpec(fig, 'futures', 'full', 10))

    # --- Section: fx ---
    # 8. FX change (close-to-close)
    fig = section_change_bar_fig(summary_daily, ['D. USD & FX'], 'FX Change (close-to-close)', 'Change', width_hint='half')
    if fig:
        figs.append(ChartSpec(fig, 'fx', 'half', 10))

    # 9. DXY 1Y
    fig = line_fig(d1y, ['DXY'], 'DXY (1Y)', 'Index', height=340, width_hint='half')
    if fig:
        figs.append(ChartSpec(fig, 'fx', 'half', 20))

    # 10. RMB change (close-to-close)
    fig = section_change_bar_fig(summary_daily, ['E. RMB'], 'RMB Change (close-to-close)', 'Change', width_hint='half')
    if fig:
        figs.append(ChartSpec(fig, 'fx', 'half', 30))

    # 11. USDCNY/CNH & Fixing 1Y
    fig = line_fig(d1y, ['USD/CNY fixing', 'USDCNY', 'USDCNH'], 'USDCNY/CNH & Fixing (1Y)', 'USD/CNY', height=340, width_hint='half')
    if fig:
        figs.append(ChartSpec(fig, 'fx', 'half', 40))

    # --- Section: commodities ---
    # 12. Commodity change (close-to-close)
    fig = section_change_bar_fig(summary_daily, ['F. Commodities'], 'Commodity Change (close-to-close)', 'Change', width_hint='half')
    if fig:
        figs.append(ChartSpec(fig, 'commodities', 'half', 10))

    # 13. Oil 1Y
    fig = line_fig(d1y, ['Brent crude', 'WTI crude'], 'Crude Oil (1Y)', 'USD', height=340, width_hint='half')
    if fig:
        figs.append(ChartSpec(fig, 'commodities', 'half', 20))

    # 14. Gold & Copper 1Y
    fig = dual_axis_line_fig(d1y, cols_left=['Gold'], cols_right=['Copper'], title='Gold & Copper (1Y)', ytitle_left='Gold (USD)', ytitle_right='Copper (USD)')
    if fig:
        figs.append(ChartSpec(fig, 'commodities', 'half', 30))

    # --- Section: longterm ---
    # 15. UST 2Y/10Y 2-year
    d2y = daily_panel if daily_panel is not None else None
    fig = line_fig(d2y, ['UST 2Y', 'UST 10Y'], 'UST 2Y/10Y (2Y daily)', 'Yield (%)', height=340, width_hint='full')
    if fig:
        figs.append(ChartSpec(fig, 'longterm', 'full', 10))

    # 16. 2s10s spread 2-year
    fig = line_fig(d2y, ['UST 2s10s spread'], '2s10s Spread (2Y daily)', 'bp', height=340, width_hint='full')
    if fig:
        figs.append(ChartSpec(fig, 'longterm', 'full', 20))

    # 17. DXY & Gold 2-year
    fig = dual_axis_line_fig(d2y, cols_left=['DXY'], cols_right=['Gold'], title='DXY & Gold (2Y daily)', ytitle_left='DXY', ytitle_right='Gold (USD)', height=340, width_hint='full')
    if fig:
        figs.append(ChartSpec(fig, 'longterm', 'full', 30))

    return figs
