#!/usr/bin/env python3
"""Kaggle notebook launcher for AI News Finder.

Run this from a Kaggle notebook after cloning the GitHub repo and installing
requirements. It forwards all normal CLI flags to ``run.py`` and defaults the
report output directory to ``/kaggle/working/reports`` when none is provided.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "run.py"


def _default_reports_dir() -> str | None:
    custom_dir = os.getenv("AI_NEWS_REPORTS_DIR")
    if custom_dir:
        return custom_dir
    if os.getenv("KAGGLE_KERNEL_RUN_TYPE") or Path("/kaggle/working").exists():
        return "/kaggle/working/reports"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch AI News Finder from a Kaggle notebook session.",
    )
    parser.add_argument(
        "--reports-dir",
        default=_default_reports_dir(),
        help="Directory where reports should be written.",
    )
    args, passthrough = parser.parse_known_args()

    if not RUNNER.is_file():
        print(f"Error: missing {RUNNER}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(RUNNER), *passthrough]
    if args.reports_dir and "--reports-dir" not in passthrough:
        cmd.extend(["--reports-dir", args.reports_dir])

    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
