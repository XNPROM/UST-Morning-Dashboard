# Source Generated with Decompyle++
# File: push_report.cpython-311.pyc (Python 3.11)

from __future__ import annotations
import os
import subprocess
from datetime import datetime
from config.settings import settings

def push_report(html_path = None, repo_root = None):
    """Git add, commit, and push the report files for the current run only."""
    if repo_root is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not html_path or not os.path.exists(html_path):
        print('No report HTML to push.')
        return
    # Derive the timestamp stem from the HTML filename, e.g. "20260428_1128"
    basename = os.path.basename(html_path)
    # morning_dashboard_20260428_1128.html -> 20260428_1128
    stem = basename.replace('morning_dashboard_', '').replace('.html', '')
    report_dir = os.path.dirname(html_path)
    # Only add files from THIS run (matching timestamp stem)
    report_files = [html_path]
    for pattern in [f'summary_{stem}.csv', f'ric_log_{stem}.csv',
                    f'ai_context_{stem}.txt']:
        candidate = os.path.join(report_dir, pattern)
        if os.path.exists(candidate):
            report_files.append(candidate)
    # Also add the latest ai_interpretation (matches date prefix)
    date_prefix = stem[:8]
    for fname in sorted(os.listdir(report_dir), reverse=True):
        if fname.startswith(f'ai_interpretation_{date_prefix}') and fname.endswith('.json'):
            report_files.append(os.path.join(report_dir, fname))
            break
    if not report_files:
        print('No report files to push.')
        return
    try:
        # Use -f to bypass .gitignore (reports/ is gitignored to prevent accumulation)
        subprocess.run(['git', 'add', '-f'] + report_files, cwd=repo_root, check=True)
        date_str = datetime.now(settings.REPORT_TZ).strftime('%Y-%m-%d %H:%M')
        msg = f'dashboard {date_str}'
        subprocess.run(['git', 'commit', '-m', msg], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(['git', 'push'], cwd=repo_root, check=True, capture_output=True)
        print(f'Pushed {len(report_files)} files to GitHub.')
    except subprocess.CalledProcessError as e:
        print(f'Git push failed: {e}')
