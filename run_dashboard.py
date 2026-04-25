#!/usr/bin/env python3
"""UST Morning Dashboard - 每日美债/汇率晨间看板

Usage:
    python run_dashboard.py              # 完整运行：拉数据+生成报告+推送
    python run_dashboard.py --no-push    # 运行但不推送到GitHub
    python run_dashboard.py --date 2026-04-23  # 指定日期调试
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from config.settings import settings
from config.assets import wanted_assets
from dates.windows import compute_report_windows
from data.fetch import download_panel
from data.derived import add_derived, slice_window
from data.validation import cross_validate, detect_anomalies, sanity_check
from analytics.summary import summarize_panel
from analytics.quality import data_quality_checks, find_blocking_quality_issues
from analytics.notes import build_morning_notes
from analytics.ai_interpreter import interpret_market
from analytics.calendar import build_trading_hours, build_event_calendar
from charts.plotly_charts import make_figures
from report.html_report import generate_html_report
from push.push_report import push_report


def build_artifact_timestamp(asof_dt: datetime, now: datetime | None = None) -> str:
    run_now = now or datetime.now(settings.REPORT_TZ)
    if run_now.tzinfo is None:
        run_now = run_now.replace(tzinfo=settings.REPORT_TZ)
    else:
        run_now = run_now.astimezone(settings.REPORT_TZ)

    if asof_dt.tzinfo is None:
        asof_dt = asof_dt.replace(tzinfo=settings.REPORT_TZ)
    else:
        asof_dt = asof_dt.astimezone(settings.REPORT_TZ)

    return f"{asof_dt.strftime('%Y%m%d')}_{run_now.strftime('%H%M')}"


def should_load_interpretation(
    summary_main: pd.DataFrame,
    blocking_quality_issues: pd.DataFrame,
) -> bool:
    if summary_main.empty:
        return False
    if blocking_quality_issues is not None and not blocking_quality_issues.empty:
        return False
    return True


def cleanup_old_reports(report_dir: str, keep_days: int = 14) -> None:
    """Delete report files older than keep_days."""
    cutoff = datetime.now() - timedelta(days=keep_days)
    for fname in os.listdir(report_dir):
        fpath = os.path.join(report_dir, fname)
        if not os.path.isfile(fpath):
            continue
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime < cutoff:
            os.remove(fpath)


def main():
    parser = argparse.ArgumentParser(description="UST Morning Dashboard")
    parser.add_argument("--no-push", action="store_true", help="Skip GitHub push")
    parser.add_argument("--date", type=str, default=None, help="Override as-of date (YYYY-MM-DD) for debugging")
    parser.add_argument(
        "--allow-blocking-quality",
        action="store_true",
        help="Allow GitHub push even when blocking quality issues are detected",
    )
    parser.add_argument(
        "--fail-on-blocking-quality",
        action="store_true",
        help="Exit with a non-zero code when blocking quality issues are detected",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("UST Morning Dashboard - 深圳早会看板")
    print("=" * 60)

    # 1. Compute windows (optionally override date for debugging)
    now = None
    if args.date:
        try:
            override = datetime.strptime(args.date, "%Y-%m-%d").replace(
                hour=9, minute=0, tzinfo=settings.REPORT_TZ
            )
            now = override
            print(f"Date override: {args.date}")
        except ValueError:
            print(f"FATAL: Invalid date format: {args.date}. Use YYYY-MM-DD.")
            sys.exit(1)

    windows = compute_report_windows(now)
    timestamp = build_artifact_timestamp(windows.asof_dt)
    print(f"As-of: {windows.asof_dt.strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"主窗口: {windows.main_start.strftime('%m-%d %H:%M')} → {windows.main_end.strftime('%m-%d %H:%M')}")
    print(f"纽约窗口: {windows.ny_start.strftime('%m-%d %H:%M')} → {windows.ny_end.strftime('%m-%d %H:%M')}")

    # 2. Open LSEG session (with retry)
    session = None
    max_retries = 3
    from auth.lseg_session import open_lseg_session, close_lseg_session
    for attempt in range(1, max_retries + 1):
        try:
            session = open_lseg_session()
            print("LSEG session opened.")
            break
        except Exception as e:
            print(f"LSEG session attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                print("Retrying in 10s...")
                time.sleep(10)
            else:
                print("FATAL: Cannot open LSEG session after retries.")
                print("Please check .env credentials and network.")
                sys.exit(1)

    try:
        # 3. Fetch data
        print("Fetching intraday data...")
        intraday_panel_raw, intraday_log = download_panel(
            wanted_assets("intraday"),
            start=windows.intraday_start,
            end=windows.intraday_end,
            interval=settings.INTRADAY_INTERVAL,
        )

        print("Fetching daily data...")
        daily_panel_raw, daily_log = download_panel(
            wanted_assets("daily"),
            start=windows.daily_start,
            end=windows.daily_end,
            interval=settings.LONG_INTERVAL,
        )

        # 4. Derived metrics
        intraday_panel = add_derived(intraday_panel_raw)
        daily_panel = add_derived(daily_panel_raw)

        # 5. Slice windows (main + NY + rolling24h)
        main_panel = slice_window(intraday_panel, windows.main_start, windows.main_end)
        ny_panel = slice_window(intraday_panel, windows.ny_start, windows.ny_end)
        rolling24_panel = slice_window(intraday_panel, windows.rolling24_start, windows.rolling24_end)

        if main_panel.empty:
            print("WARNING: Main panel is empty! LSEG data may be unavailable.")

        # 6. Summaries
        summary_main = summarize_panel(main_panel, "深圳早会主窗口")
        summary_ny = summarize_panel(ny_panel, "纽约交易时段")
        summary_24h = summarize_panel(rolling24_panel, "滚动24小时")

        # 7. Validation
        print("Running data validation...")
        cv_issues = cross_validate(intraday_panel, daily_panel, summary_main)
        anomaly_issues = detect_anomalies(main_panel)
        sanity_issues = sanity_check(main_panel)
        all_validation_issues = cv_issues + anomaly_issues + sanity_issues

        # 8. Quality checks
        quality_df = data_quality_checks(
            intraday_log, daily_log, main_panel, daily_panel,
            windows.target_fixing_date, all_validation_issues,
        )
        blocking_quality_issues = find_blocking_quality_issues(quality_df)
        if not blocking_quality_issues.empty:
            print("Blocking quality issues detected:")
            for _, row in blocking_quality_issues.head(5).iterrows():
                print(f"  - [{row['Severity']}] {row['Asset']}: {row['Issue']}")

        # 9. Morning notes
        morning_notes = build_morning_notes(summary_main)

        # 10. AI interpretation (two-phase: load existing or save context for later)
        print("Checking AI interpretation...")
        if should_load_interpretation(summary_main, blocking_quality_issues):
            interpretation = interpret_market(
                summary_main, summary_24h, daily_panel, quality_df, windows,
                timestamp=timestamp,
            )
            if interpretation:
                print("AI interpretation loaded.")
            else:
                print("AI interpretation not yet generated. Context file saved.")
                print("  -> In Claude Code: read the context file and generate interpretation")
        else:
            interpretation = None
            print("Skipping AI interpretation because the current batch is not suitable for analysis text.")

        # 11. Charts (include rolling24h and NY panels)
        print("Generating charts...")
        figs = make_figures(main_panel, summary_main, daily_panel, rolling24_panel, ny_panel)

        # 12. Calendar and trading hours
        trading_hours = build_trading_hours()
        event_calendar = build_event_calendar(windows)

        # 13. Generate report
        print("Generating HTML report...")
        all_logs = pd.concat([intraday_log.assign(freq="5min"), daily_log.assign(freq="daily")], ignore_index=True)
        html_path, csv_path, log_path = generate_html_report(
            summary_main=summary_main,
            summary_24h=summary_24h,
            summary_ny=summary_ny,
            morning_notes=morning_notes,
            quality_df=quality_df,
            figs=figs,
            daily_panel=daily_panel,
            all_logs=all_logs,
            windows=windows,
            trading_hours=trading_hours,
            event_calendar=event_calendar,
            interpretation=interpretation,
            timestamp=timestamp,
        )

        print(f"\nOutput:")
        print(f"  HTML: {html_path}")
        print(f"  CSV:  {csv_path}")
        print(f"  Log:  {log_path}")

        # 14. Cleanup old reports (keep last 14 days)
        try:
            cleanup_old_reports(settings.OUTPUT_DIR, keep_days=14)
        except Exception as e:
            print(f"Cleanup warning: {e}")

        # 15. Push to GitHub
        if not args.no_push:
            if not blocking_quality_issues.empty and not args.allow_blocking_quality:
                print("Skipping GitHub push because blocking quality issues were detected.")
                print("Re-run with --allow-blocking-quality if you really want to publish this report.")
            else:
                print("Pushing to GitHub...")
                success = push_report(html_path)
                if not success:
                    print("Warning: GitHub push failed. Report files are still on disk.")
        else:
            print("Skipping GitHub push (--no-push).")

        if not blocking_quality_issues.empty and args.fail_on_blocking_quality:
            print("Failing run because blocking quality issues were detected.")
            sys.exit(2)

        print("\nDone!")

    finally:
        if session is not None:
            close_lseg_session(session)
            print("LSEG session closed.")


if __name__ == "__main__":
    main()
