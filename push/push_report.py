# Source Generated with Decompyle++
# File: push_report.cpython-311.pyc (Python 3.11)

from __future__ import annotations
import glob
import os
import subprocess
from datetime import datetime
from config.settings import settings

def push_report(html_path = None, repo_root = None):
    """Git add, commit, and push the report files."""
    if repo_root is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    report_dir = os.path.dirname(html_path) if html_path else settings.OUTPUT_DIR
    report_files = glob.glob(os.path.join(report_dir, '*.html'))
    report_files.extend(glob.glob(os.path.join(report_dir, 'summary_*.csv')))
    report_files.extend(glob.glob(os.path.join(report_dir, 'ric_log_*.csv')))
    report_files.extend(glob.glob(os.path.join(report_dir, 'ai_context_*.txt')))
    report_files.extend(glob.glob(os.path.join(report_dir, 'ai_interpretation_*.json')))
    if not report_files:
        print('No report files to push.')
        return
    try:
        subprocess.run(['git', 'add'] + report_files, cwd=repo_root, check=True)
        date_str = datetime.now(settings.REPORT_TZ).strftime('%Y-%m-%d %H:%M')
        msg = f'dashboard {date_str}'
        subprocess.run(['git', 'commit', '-m', msg], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(['git', 'push'], cwd=repo_root, check=True, capture_output=True)
        print(f'Pushed {len(report_files)} files to GitHub.')
    except subprocess.CalledProcessError as e:
        print(f'Git push failed: {e}')
