from __future__ import annotations

import glob
import os
import subprocess
from datetime import datetime

from config.settings import settings


def push_report(html_path: str | None = None, repo_root: str | None = None) -> bool:
    repo_root = repo_root or settings.PROJECT_ROOT

    timestamp = datetime.now(settings.REPORT_TZ).strftime("%Y-%m-%d %H:%M")

    try:
        if html_path:
            html_files = [html_path]
        else:
            html_files = glob.glob(os.path.join(settings.OUTPUT_DIR, "*.html"))

        if not html_files:
            print("[Push] No HTML files to commit.")
            return True

        repo_paths = [os.path.relpath(f, repo_root) for f in html_files]

        for f in repo_paths:
            subprocess.run(
                ["git", "add", f],
                cwd=repo_root, capture_output=True, text=True, check=True,
            )

        # Check if there are staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_root, capture_output=True, text=True,
        )
        if result.returncode == 0:
            print("[Push] No new changes to commit.")
            return True

        # Commit
        subprocess.run(
            ["git", "commit", "--only", "-m", f"dashboard {timestamp}", "--", *repo_paths],
            cwd=repo_root, capture_output=True, text=True, check=True,
        )

        # Push
        result = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            cwd=repo_root, capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"[Push] git push failed: {result.stderr}")
            return False

        print(f"[Push] Report pushed successfully: dashboard {timestamp}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"[Push] Git operation failed: {e.stderr}")
        return False
    except Exception as e:
        print(f"[Push] Unexpected error: {e}")
        return False
