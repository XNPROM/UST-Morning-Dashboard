from __future__ import annotations

import inspect
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, date
from unittest import mock
from types import SimpleNamespace

import pandas as pd
import plotly.graph_objects as go

import run_dashboard
from auth.lseg_session import open_lseg_session
from analytics.quality import compute_quality_grade, find_blocking_quality_issues
from charts.plotly_charts import line_fig
from config.settings import settings
from data.validation import cross_validate
from push.push_report import push_report
from report.html_report import generate_html_report
from dates.windows import ReportWindows


class RegressionTests(unittest.TestCase):
    def test_cross_validate_handles_empty_summary(self) -> None:
        issues = cross_validate(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        self.assertEqual(issues, [])

    def test_line_fig_normalizes_against_first_observation(self) -> None:
        panel = pd.DataFrame(
            {"A": [10.0, 20.0, 15.0]},
            index=pd.date_range("2026-01-01", periods=3, freq="h", tz="Asia/Shanghai"),
        )

        fig = line_fig(panel, ["A"], "demo", "Start=100", normalize=True)

        self.assertEqual([float(y) for y in fig.data[0].y], [100.0, 200.0, 150.0])

    def test_generate_html_report_accepts_timestamp_override(self) -> None:
        self.assertIn("timestamp", inspect.signature(generate_html_report).parameters)

        with tempfile.TemporaryDirectory() as tmpdir:
            old_output_dir = os.environ.get("OUTPUT_DIR")
            os.environ["OUTPUT_DIR"] = tmpdir
            try:
                windows = ReportWindows(
                    asof_dt=datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
                    asof_date=date(2026, 4, 23),
                    prev_cn_day=date(2026, 4, 22),
                    prev_us_day=date(2026, 4, 22),
                    main_start=datetime(2026, 4, 22, 16, 0, tzinfo=settings.REPORT_TZ),
                    main_end=datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
                    ny_start=datetime(2026, 4, 22, 20, 0, tzinfo=settings.REPORT_TZ),
                    ny_end=datetime(2026, 4, 23, 5, 0, tzinfo=settings.REPORT_TZ),
                    rolling24_start=datetime(2026, 4, 22, 9, 0, tzinfo=settings.REPORT_TZ),
                    rolling24_end=datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
                    intraday_start=datetime(2026, 4, 20, 9, 0, tzinfo=settings.REPORT_TZ),
                    intraday_end=datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
                    daily_start=datetime(2025, 1, 1, 9, 0, tzinfo=settings.REPORT_TZ),
                    daily_end=datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
                    target_fixing_date=date(2026, 4, 23),
                )

                html_path, csv_path, log_path = generate_html_report(
                    summary_main=pd.DataFrame(),
                    summary_24h=pd.DataFrame(),
                    summary_ny=pd.DataFrame(),
                    morning_notes=[],
                    quality_df=pd.DataFrame([{"Severity": "OK", "Asset": "ALL", "Issue": "ok", "Detail": "ok"}]),
                    figs=[go.Figure()],
                    daily_panel=pd.DataFrame(),
                    all_logs=pd.DataFrame(
                        columns=["freq", "section", "group", "name", "ric", "field", "rows", "status", "error"]
                    ),
                    windows=windows,
                    trading_hours=pd.DataFrame(),
                    event_calendar=pd.DataFrame(),
                    interpretation=None,
                    timestamp="20260423_2027",
                )
            finally:
                if old_output_dir is None:
                    os.environ.pop("OUTPUT_DIR", None)
                else:
                    os.environ["OUTPUT_DIR"] = old_output_dir

        self.assertTrue(html_path.endswith("20260423_2027.html"))
        self.assertTrue(csv_path.endswith("20260423_2027.csv"))
        self.assertTrue(log_path.endswith("20260423_2027.csv"))

    def test_build_artifact_timestamp_uses_business_date_prefix(self) -> None:
        self.assertTrue(hasattr(run_dashboard, "build_artifact_timestamp"))
        timestamp = run_dashboard.build_artifact_timestamp(
            datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
            datetime(2026, 4, 25, 20, 27, tzinfo=settings.REPORT_TZ),
        )
        self.assertEqual(timestamp, "20260423_2027")

    def test_compute_quality_grade_applies_cross_asset_issues_to_implicated_sections(self) -> None:
        quality_df = pd.DataFrame(
            [
                {
                    "Severity": "HIGH",
                    "Asset": "UST 10Y vs TY 10Y Treasury Fut",
                    "Issue": "direction mismatch",
                    "Detail": "demo",
                }
            ]
        )

        grades = compute_quality_grade(quality_df)

        self.assertEqual(grades["A. Rates"], "C")
        self.assertEqual(grades["C. Treasury Futures"], "C")

    def test_find_blocking_quality_issues_returns_high_severity_rows(self) -> None:
        quality_df = pd.DataFrame(
            [
                {"Severity": "LOW", "Asset": "USD/CNY fixing", "Issue": "stale", "Detail": "demo"},
                {"Severity": "HIGH", "Asset": "UST 10Y", "Issue": "bad data", "Detail": "demo"},
            ]
        )

        blocking = find_blocking_quality_issues(quality_df)

        self.assertEqual(blocking[["Severity", "Asset"]].to_dict("records"), [{"Severity": "HIGH", "Asset": "UST 10Y"}])

    def test_find_blocking_quality_issues_ignores_ok_rows(self) -> None:
        quality_df = pd.DataFrame(
            [
                {"Severity": "OK", "Asset": "ALL", "Issue": "ok", "Detail": "demo"},
                {"Severity": "LOW", "Asset": "USD/CNY fixing", "Issue": "stale", "Detail": "demo"},
            ]
        )

        blocking = find_blocking_quality_issues(quality_df)

        self.assertTrue(blocking.empty)

    def test_cross_validate_skips_intraday_daily_level_mismatch_check(self) -> None:
        intraday_panel = pd.DataFrame(
            {
                "UST 2Y": [3.7825, 3.84085],
            },
            index=pd.to_datetime(
                ["2026-04-24 00:00:00+08:00", "2026-04-24 08:55:00+08:00"]
            ),
        )
        daily_panel = pd.DataFrame(
            {
                "UST 2Y": [3.7825],
            },
            index=pd.to_datetime(["2026-04-24 00:00:00+08:00"]),
        )
        summary_main = pd.DataFrame(
            [
                {"Asset": "UST 2Y", "Change": 0.01},
                {"Asset": "TU 2Y Treasury Fut", "Change": -0.02},
            ]
        )

        issues = cross_validate(intraday_panel, daily_panel, summary_main)

        intraday_daily_issues = [issue for issue in issues if issue["Asset"] == "UST 2Y"]
        self.assertEqual(intraday_daily_issues, [])

    def test_push_report_commits_only_report_paths(self) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd, cwd=None, capture_output=None, text=None, check=False):
            calls.append(cmd)
            if cmd[:3] == ["git", "diff", "--cached"]:
                return subprocess.CompletedProcess(cmd, 1)
            return subprocess.CompletedProcess(cmd, 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "report.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write("<html></html>")

            with mock.patch("push.push_report.subprocess.run", side_effect=fake_run), mock.patch("builtins.print"):
                success = push_report(html_path=html_path, repo_root=tmpdir)

        self.assertTrue(success)
        commit_cmd = next(cmd for cmd in calls if cmd[:2] == ["git", "commit"])
        self.assertIn("--only", commit_cmd)
        self.assertIn("--", commit_cmd)
        self.assertEqual(commit_cmd[-1], "report.html")

    def test_open_lseg_session_raises_when_session_never_opens(self) -> None:
        class FakeSession:
            def __init__(self) -> None:
                self.open_state = SimpleNamespace(name="Closed")

            def open(self) -> None:
                self.open_state = SimpleNamespace(name="Closed")

            def close(self) -> None:
                return None

        fake_session = FakeSession()
        fake_definition = SimpleNamespace(get_session=lambda: fake_session)
        fake_ld = SimpleNamespace(
            session=SimpleNamespace(
                platform=SimpleNamespace(
                    Definition=lambda **kwargs: fake_definition,
                    GrantPassword=lambda username, password: (username, password),
                ),
                set_default=lambda session: None,
            )
        )

        with mock.patch.dict(sys.modules, {"lseg.data": fake_ld}):
            with self.assertRaisesRegex(RuntimeError, "did not open successfully"):
                open_lseg_session()

    def test_should_load_interpretation_requires_data_and_no_blockers(self) -> None:
        blocking = pd.DataFrame([{"Severity": "HIGH", "Asset": "UST 10Y"}])

        self.assertFalse(run_dashboard.should_load_interpretation(pd.DataFrame(), pd.DataFrame()))
        self.assertFalse(run_dashboard.should_load_interpretation(pd.DataFrame([{"Asset": "UST 10Y"}]), blocking))
        self.assertTrue(run_dashboard.should_load_interpretation(pd.DataFrame([{"Asset": "UST 10Y"}]), pd.DataFrame()))

    def test_generate_html_report_surfaces_blocking_data_banner(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_output_dir = os.environ.get("OUTPUT_DIR")
            os.environ["OUTPUT_DIR"] = tmpdir
            try:
                windows = ReportWindows(
                    asof_dt=datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
                    asof_date=date(2026, 4, 23),
                    prev_cn_day=date(2026, 4, 22),
                    prev_us_day=date(2026, 4, 22),
                    main_start=datetime(2026, 4, 22, 16, 0, tzinfo=settings.REPORT_TZ),
                    main_end=datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
                    ny_start=datetime(2026, 4, 22, 20, 0, tzinfo=settings.REPORT_TZ),
                    ny_end=datetime(2026, 4, 23, 5, 0, tzinfo=settings.REPORT_TZ),
                    rolling24_start=datetime(2026, 4, 22, 9, 0, tzinfo=settings.REPORT_TZ),
                    rolling24_end=datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
                    intraday_start=datetime(2026, 4, 20, 9, 0, tzinfo=settings.REPORT_TZ),
                    intraday_end=datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
                    daily_start=datetime(2025, 1, 1, 9, 0, tzinfo=settings.REPORT_TZ),
                    daily_end=datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
                    target_fixing_date=date(2026, 4, 23),
                )

                html_path, _, _ = generate_html_report(
                    summary_main=pd.DataFrame(),
                    summary_24h=pd.DataFrame(),
                    summary_ny=pd.DataFrame(),
                    morning_notes=[],
                    quality_df=pd.DataFrame(
                        [{"Severity": "HIGH", "Asset": "UST 10Y", "Issue": "fetch failed", "Detail": "demo"}]
                    ),
                    figs=[go.Figure()],
                    daily_panel=pd.DataFrame(),
                    all_logs=pd.DataFrame(
                        columns=["freq", "section", "group", "name", "ric", "field", "rows", "status", "error"]
                    ),
                    windows=windows,
                    trading_hours=pd.DataFrame(),
                    event_calendar=pd.DataFrame(),
                    interpretation=None,
                    timestamp="20260423_2027",
                )
                with open(html_path, "r", encoding="utf-8") as f:
                    html = f.read()
            finally:
                if old_output_dir is None:
                    os.environ.pop("OUTPUT_DIR", None)
                else:
                    os.environ["OUTPUT_DIR"] = old_output_dir

        self.assertIn("本批次数据存在关键缺口", html)


if __name__ == "__main__":
    unittest.main()
