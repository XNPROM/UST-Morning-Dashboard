from __future__ import annotations

import plotly.graph_objects as go

from config.settings import settings
from analytics.summary import rows_by_section


CHART_COLORS = [
    "#0f766e",
    "#10233f",
    "#b45309",
    "#2563eb",
    "#b91c1c",
    "#7c3aed",
]


def _apply_chart_style(fig: go.Figure, title: str, ytitle: str, height: int, bottom_margin: int = 40) -> go.Figure:
    fig.update_layout(
        title=dict(
            text=title,
            x=0.02,
            xanchor="left",
            font=dict(
                family='"Georgia", "Source Han Serif SC", "STSong", serif',
                size=17,
                color="#10233f",
            ),
        ),
        template=settings.PLOTLY_TEMPLATE,
        colorway=CHART_COLORS,
        hovermode="x unified",
        height=height,
        margin=dict(l=46, r=18, t=60, b=bottom_margin),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="left",
            x=0,
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="#d9e2ec",
            borderwidth=1,
            font=dict(
                family='"Aptos", "Segoe UI Variable", "PingFang SC", "Microsoft YaHei", sans-serif',
                size=11,
                color="#334155",
            ),
        ),
        font=dict(
            family='"Aptos", "Segoe UI Variable", "PingFang SC", "Microsoft YaHei", sans-serif',
            size=12,
            color="#334155",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        yaxis_title=ytitle,
        xaxis_title="",
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor="#cbd5e1",
            font=dict(color="#0f172a"),
        ),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#e5e7eb",
        linecolor="#cbd5e1",
        zerolinecolor="#cbd5e1",
        tickfont=dict(color="#475569"),
        title_font=dict(color="#475569"),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#e5e7eb",
        linecolor="#cbd5e1",
        zerolinecolor="#cbd5e1",
        tickfont=dict(color="#475569"),
        title_font=dict(color="#475569"),
    )
    return fig


def existing(panel, cols: list[str]) -> list[str]:
    return [c for c in cols if c in panel.columns and panel[c].dropna().shape[0] >= 2]


def line_fig(
    panel, cols: list[str], title: str, ytitle: str,
    normalize: bool = False, height: int = 420,
) -> go.Figure:
    cols = existing(panel, cols)
    fig = go.Figure()
    if not cols:
        _apply_chart_style(fig, f"{title}（无可用数据）", ytitle, height)
        return fig

    for col in cols:
        s = panel[col].dropna()
        if normalize:
            base = float(s.iloc[0])
            y = s if base == 0 else s / base * 100
        else:
            y = s
        fig.add_trace(go.Scatter(
            x=s.index.tz_convert(settings.REPORT_TZ),
            y=y,
            mode="lines",
            name=col,
            line=dict(width=2.4),
            hovertemplate="%{x}<br>%{y:.4f}<extra>%{fullData.name}</extra>",
        ))

    return _apply_chart_style(fig, title, ytitle, height)


def change_bar_fig(summary, sections: list[str], title: str) -> go.Figure:
    df = rows_by_section(summary, sections)
    if df.empty:
        fig = go.Figure()
        _apply_chart_style(fig, f"{title}（无可用数据）", "Change", 360, bottom_margin=80)
        return fig

    df = df.copy().dropna(subset=["Change Display"])
    marker_colors = ["#24564f" if val >= 0 else "#b16d2e" for val in df["Change Display"]]
    fig = go.Figure(go.Bar(
        x=df["Asset"],
        y=df["Change Display"],
        text=df["Change Text"],
        textposition="outside",
        hovertemplate="%{x}<br>%{y:.4f} %{customdata}<extra></extra>",
        customdata=df["Change Unit"],
        marker=dict(color=marker_colors, line=dict(color="#ffffff", width=1)),
    ))
    _apply_chart_style(fig, title, "Change", 380, bottom_margin=88)
    fig.update_xaxes(tickangle=-25)
    fig.add_hline(y=0, line_width=1)
    return fig


def make_figures(main_panel, summary_main, daily_panel, rolling24_panel=None, ny_panel=None) -> list[go.Figure]:
    figs = []
    figs.append(line_fig(main_panel, ["UST 2Y", "UST 5Y", "UST 10Y", "UST 30Y"], "主窗口：美债名义收益率", "Yield (%)"))
    figs.append(change_bar_fig(summary_main, ["A. Rates", "B. Real & Inflation"], "主窗口：利率、曲线、BEI变化"))
    figs.append(line_fig(main_panel, ["TIPS real 5Y", "TIPS real 10Y", "TIPS real 30Y"], "主窗口：TIPS真实收益率", "Real yield (%)"))
    figs.append(line_fig(main_panel, ["BEI 5Y", "BEI 10Y", "BEI 30Y"], "主窗口：盈亏平衡通胀 BEI", "BEI (%)"))
    figs.append(line_fig(main_panel, ["TU 2Y Treasury Fut", "FV 5Y Treasury Fut", "TY 10Y Treasury Fut", "US 30Y Treasury Fut"], "主窗口：CBOT美债期货（归一化）", "Start=100", normalize=True))
    figs.append(line_fig(main_panel, ["DXY"], "主窗口：美元指数 DXY", "Index"))
    figs.append(line_fig(main_panel, ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD"], "主窗口：G10主要汇率（归一化）", "Start=100", normalize=True))
    figs.append(line_fig(main_panel, ["USDCNY", "USDCNH"], "主窗口：USDCNY / USDCNH", "Spot"))
    figs.append(line_fig(daily_panel.tail(260), ["USD/CNY fixing", "USDCNY", "USDCNH"], "近一年：人民币中间价 vs CNY/CNH", "USD/CNY"))
    figs.append(line_fig(main_panel, ["Brent crude", "WTI crude", "Gold", "Copper"], "主窗口：油铜金（归一化）", "Start=100", normalize=True))
    figs.append(line_fig(daily_panel.tail(260), ["UST 2Y", "UST 5Y", "UST 10Y", "UST 30Y"], "近一年：美债收益率", "Yield (%)"))
    figs.append(line_fig(daily_panel.tail(260), ["BEI 5Y", "BEI 10Y", "BEI 30Y"], "近一年：BEI", "BEI (%)"))
    if rolling24_panel is not None and not rolling24_panel.empty:
        figs.append(line_fig(rolling24_panel, ["UST 2Y", "UST 5Y", "UST 10Y", "UST 30Y"], "滚动24h：美债名义收益率", "Yield (%)"))
        figs.append(line_fig(rolling24_panel, ["DXY"], "滚动24h：美元指数 DXY", "Index"))
    if ny_panel is not None and not ny_panel.empty:
        figs.append(line_fig(ny_panel, ["UST 2Y", "UST 5Y", "UST 10Y", "UST 30Y"], "纽约时段：美债名义收益率", "Yield (%)"))
        figs.append(line_fig(ny_panel, ["DXY"], "纽约时段：美元指数 DXY", "Index"))
    return figs
