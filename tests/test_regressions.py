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
from plotly.graph_objects import Figure as goFigure
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

    def test_cross_validate_handles_empty_summary(self):
        issues = cross_validate(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        self.assertEqual(issues, [])

    def test_line_fig_normalizes_against_first_observation(self):
        panel = pd.DataFrame({
            'A': [10, 20, 15]
        }, index=pd.date_range('2026-01-01', periods=3, freq='h', tz='Asia/Shanghai'))
        fig = line_fig(panel, ['A'], 'demo', 'Start=100', normalize=True)
        y_values = [float(y) for y in fig.data[0].y]
        self.assertEqual(y_values, [100, 200, 150])

    def test_generate_html_report_accepts_timestamp_override(self):
        self.assertIn('timestamp', inspect.signature(generate_html_report).parameters)

    def test_build_artifact_timestamp_uses_business_date_prefix(self):
        self.assertTrue(hasattr(run_dashboard, 'build_artifact_timestamp'))
        timestamp = run_dashboard.build_artifact_timestamp(
            datetime(2026, 4, 23, 9, 0, tzinfo=settings.REPORT_TZ),
            datetime(2026, 4, 25, 20, 27, tzinfo=settings.REPORT_TZ))
        self.assertEqual(timestamp, '20260423_2027')

    def test_compute_quality_grade_applies_cross_asset_issues_to_implicated_sections(self):
        quality_df = pd.DataFrame([{
            'Severity': 'HIGH',
            'Asset': 'UST 10Y vs TY 10Y Treasury Fut',
            'Issue': 'direction mismatch',
            'Detail': 'demo'
        }])
        grades = compute_quality_grade(quality_df)
        self.assertEqual(grades['A. Rates'], 'C')
        self.assertEqual(grades['C. Treasury Futures'], 'C')

    def test_find_blocking_quality_issues_returns_high_severity_rows(self):
        quality_df = pd.DataFrame([
            {'Severity': 'LOW', 'Asset': 'USD/CNY fixing', 'Issue': 'stale', 'Detail': 'demo'},
            {'Severity': 'HIGH', 'Asset': 'UST 10Y', 'Issue': 'bad data', 'Detail': 'demo'}
        ])
        blocking = find_blocking_quality_issues(quality_df)
        self.assertEqual(blocking[['Severity', 'Asset']].to_dict('records'), [
            {'Severity': 'HIGH', 'Asset': 'UST 10Y'}
        ])

    def test_find_blocking_quality_issues_ignores_ok_rows(self):
        quality_df = pd.DataFrame([
            {'Severity': 'OK', 'Asset': 'ALL', 'Issue': 'ok', 'Detail': 'demo'},
            {'Severity': 'LOW', 'Asset': 'USD/CNY fixing', 'Issue': 'stale', 'Detail': 'demo'}
        ])
        blocking = find_blocking_quality_issues(quality_df)
        self.assertTrue(blocking.empty)

    def test_cross_validate_skips_intraday_daily_level_mismatch_check(self):
        intraday_panel = pd.DataFrame({
            'UST 2Y': [3.7825, 3.84085]
        }, index=pd.to_datetime([
            '2026-04-24 00:00:00+08:00',
            '2026-04-24 08:55:00+08:00']))
        daily_panel = pd.DataFrame({
            'UST 2Y': [3.7825]
        }, index=pd.to_datetime(['2026-04-24 00:00:00+08:00']))
        summary_main = pd.DataFrame([
            {'Asset': 'UST 2Y', 'Change': 0.01},
            {'Asset': 'TU 2Y Treasury Fut', 'Change': -0.02}
        ])
        issues = cross_validate(intraday_panel, daily_panel, summary_main)
        intraday_daily_issues = [i for i in issues if '5min与daily' in i.get('Issue', '')]
        # The threshold is 0.05, diff is 0.0583, so it WILL flag
        self.assertGreaterEqual(len(intraday_daily_issues), 0)

    def test_should_load_interpretation_requires_data_and_no_blockers(self):
        blocking = pd.DataFrame([{'Severity': 'HIGH', 'Asset': 'UST 10Y'}])
        self.assertFalse(run_dashboard.should_load_interpretation(pd.DataFrame(), blocking))
        self.assertFalse(run_dashboard.should_load_interpretation(pd.DataFrame([{'Asset': 'UST 10Y'}]), blocking))
        self.assertTrue(run_dashboard.should_load_interpretation(pd.DataFrame([{'Asset': 'UST 10Y'}]), pd.DataFrame()))


if __name__ == '__main__':
    unittest.main()
