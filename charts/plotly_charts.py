from __future__ import annotations

import plotly.graph_objects as go

from config.settings import settings
from analytics.summary import rows_by_section


def existing(panel, cols: list[str]) -> list[str]:
    return [c for c in cols if c in panel.columns and panel[c].dropna().shape[0] >= 2]


def line_fig(
    panel, cols: list[str], title: str, ytitle: str,
    normalize: bool = False, height: int = 420,
) -> go.Figure:
    cols = existing(panel, cols)
    fig = go.Figure()
    if not cols:
        fig.update_layout(title=f"{title}（无可用数据）", template=settings.PLOTLY_TEMPLATE, height=height)
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
            hovertemplate="%{x}<br>%{y:.4f}<extra>%{fullData.name}</extra>",
        ))

    fig.update_layout(
        title=title,
        template=settings.PLOTLY_TEMPLATE,
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=20, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        yaxis_title=ytitle,
        xaxis_title="",
    )
    return fig


def change_bar_fig(summary, sections: list[str], title: str) -> go.Figure:
    df = rows_by_section(summary, sections)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=f"{title}（无可用数据）", template=settings.PLOTLY_TEMPLATE, height=360)
        return fig

    df = df.copy().dropna(subset=["Change Display"])
    fig = go.Figure(go.Bar(
        x=df["Asset"],
        y=df["Change Display"],
        text=df["Change Text"],
        textposition="outside",
        hovertemplate="%{x}<br>%{y:.4f} %{customdata}<extra></extra>",
        customdata=df["Change Unit"],
    ))
    fig.update_layout(
        title=title,
        template=settings.PLOTLY_TEMPLATE,
        height=380,
        margin=dict(l=40, r=20, t=60, b=80),
        yaxis_title="Change",
        xaxis_tickangle=-25,
    )
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
