'''UST Morning Dashboard - 每日美债/汇率晨间看板

Usage:
    python run_dashboard.py              # 完整运行：拉数据+生成报告+推送
    python run_dashboard.py --no-push    # 运行但不推送到GitHub
    python run_dashboard.py --date 2026-04-23  # 指定日期调试
'''
from __future__ import annotations
import argparse
import os
import sys
import time
from datetime import datetime, timedelta
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from config.settings import settings
from config.assets import wanted_assets
from dates.windows import compute_report_windows
from data.fetch import download_panel
from data.derived import add_derived, slice_window, clean_panel, resample_panel
from data.validation import cross_validate, detect_anomalies, sanity_check
from analytics.summary import summarize_panel
from analytics.quality import data_quality_checks, find_blocking_quality_issues
from analytics.notes import build_morning_notes
from analytics.ai_interpreter import interpret_market
from analytics.calendar import build_trading_hours, build_event_calendar
from charts.plotly_charts import make_figures
from report.html_report import generate_html_report
from push.push_report import push_report


def build_artifact_timestamp(asof_dt = None, now = None):
    if not now:
        now = datetime.now(settings.REPORT_TZ)
    if not asof_dt:
        asof_dt = now
    date_prefix = asof_dt.strftime('%Y%m%d')
    time_suffix = now.strftime('%H%M')
    return f'{date_prefix}_{time_suffix}'


def should_load_interpretation(summary_main = None, blocking_quality_issues = None):
    if summary_main is None or summary_main.empty:
        return False
    if blocking_quality_issues is not None and not blocking_quality_issues.empty:
        return False
    return True


def cleanup_old_reports(report_dir = None, keep_days = None):
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
    parser = argparse.ArgumentParser(description='UST Morning Dashboard')
    parser.add_argument('--no-push', action='store_true', help='Skip GitHub push')
    parser.add_argument('--date', type=str, default=None, help='Override as-of date (YYYY-MM-DD) for debugging')
    parser.add_argument('--allow-blocking-quality', action='store_true', help='Allow GitHub push even when blocking quality issues are detected')
    parser.add_argument('--fail-on-blocking-quality', action='store_true', help='Exit with a non-zero code when blocking quality issues are detected')
    args = parser.parse_args()
    print('============================================================')
    print('UST Morning Dashboard - 深圳早会看板')
    print('============================================================')
    now = datetime.now(settings.REPORT_TZ)
    if args.date:
        override = datetime.strptime(args.date, '%Y-%m-%d').replace(hour=9, minute=0, tzinfo=settings.REPORT_TZ)
        now = override
        print(f'Date override: {args.date}')
    print(f'Run time: {now.strftime("%Y-%m-%d %H:%M:%S %Z")}')
    windows = compute_report_windows(asof_dt=now)
    print(f'As-of: {windows.asof_dt.strftime("%Y-%m-%d %H:%M")}')
    print(f'Main window: {windows.main_start.strftime("%m-%d %H:%M")} -> {windows.main_end.strftime("%m-%d %H:%M")}')
    try:
        session = None
        from auth.lseg_session import open_lseg_session, close_lseg_session
        session = open_lseg_session()
        assets_intra = wanted_assets(freq='intraday')
        assets_daily = wanted_assets(freq='daily')
        # Fetch intraday from rolling_24h_start so the 24h chart has full data
        fetch_start = min(windows.rolling_24h_start, windows.main_start)
        print('Fetching intraday data...')
        intraday_panel, intraday_logs = download_panel(assets_intra, fetch_start, windows.main_end, session=session)
        print('Fetching daily data (2-year history)...')
        from datetime import date as date_cls
        history_start_dt = datetime(windows.history_start.year, windows.history_start.month, windows.history_start.day, tzinfo=settings.REPORT_TZ)
        history_end_dt = windows.asof_dt.replace(hour=23, minute=59, second=59, microsecond=0)
        daily_panel, daily_logs = download_panel(assets_daily, history_start_dt, history_end_dt, interval='daily', session=session)
    finally:
        if session is not None:
            try:
                from auth.lseg_session import close_lseg_session
                close_lseg_session(session)
            except Exception:
                pass
    print('Computing derived metrics...')
    intraday_panel = add_derived(intraday_panel)
    daily_panel = add_derived(daily_panel)
    print('Resampling daily panel to weekly / monthly...')
    weekly_panel = resample_panel(daily_panel, rule='W-FRI')
    monthly_panel = resample_panel(daily_panel, rule='ME')
    print('Cleaning data (ffill gaps, remove spikes)...')
    intraday_panel = clean_panel(intraday_panel)
    main_panel = slice_window(intraday_panel, windows.main_start, windows.main_end)
    rolling24_panel = slice_window(intraday_panel, windows.rolling_24h_start, windows.main_end)
    ny_panel = slice_window(intraday_panel, windows.ny_start, windows.ny_end)
    print('Running validation...')
    validation_issues = []
    validation_issues.extend(detect_anomalies(main_panel))
    validation_issues.extend(sanity_check(main_panel))
    cross_issues = cross_validate(intraday_panel, daily_panel, summarize_panel(main_panel))
    validation_issues.extend(cross_issues)
    print('Generating summaries...')
    summary_main = summarize_panel(main_panel, 'main')
    summary_24h = summarize_panel(rolling24_panel, '24h')
    summary_ny = summarize_panel(ny_panel, 'ny')
    print('Running quality checks...')
    quality_df = data_quality_checks(
        intraday_log=intraday_logs,
        daily_log=daily_logs,
        main_panel=main_panel,
        daily_panel=daily_panel,
        target_fixing_date=windows.target_fixing_date,
        validation_issues=validation_issues if validation_issues else None
    )
    blocking_issues = find_blocking_quality_issues(quality_df)
    if not blocking_issues.empty:
        print(f'BLOCKING: {len(blocking_issues)} high-severity quality issues found.')
        if not args.allow_blocking_quality:
            print('Blocking push. Use --allow-blocking-quality to override.')
    print('Building morning notes...')
    morning_notes = build_morning_notes(summary_main)
    print('Generating AI interpretation context...')
    timestamp = build_artifact_timestamp(windows.asof_dt, now)
    ai_result = interpret_market(summary_main, summary_24h, daily_panel, quality_df, windows, timestamp)
    interpretation = ai_result if isinstance(ai_result, dict) else None
    print('Generating charts...')
    figs = make_figures(main_panel, summary_main, daily_panel, rolling24_panel, ny_panel,
                        weekly_panel=weekly_panel, monthly_panel=monthly_panel)
    print('Generating HTML report...')
    trading_hours = build_trading_hours()
    event_calendar = build_event_calendar(windows)
    all_logs = pd.concat([intraday_logs, daily_logs], ignore_index=True) if not intraday_logs.empty or not daily_logs.empty else pd.DataFrame()
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
    print(f'Report: {html_path}')
    if not args.no_push:
        print('Pushing to GitHub...')
        push_report(html_path, repo_root=os.path.dirname(os.path.abspath(__file__)))
    # Cleanup old reports
    cleanup_old_reports(settings.OUTPUT_DIR, settings.CLEANUP_DAYS)
    print('Done.')


if __name__ == '__main__':
    main()
