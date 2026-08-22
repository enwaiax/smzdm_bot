"""
SMZDM QingLong entrypoint
Repository: https://github.com/enwaiax/smzdm_bot
0 9 * * * smzdm_ql.py
const $ = new Env("什么值得买签到");
"""

import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent


def main() -> int:
    """Install the checked-out package and run it once."""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--editable", "."],
        cwd=REPO_DIR,
        check=True,
    )
    completed = subprocess.run(
        [sys.executable, "-m", "smzdm_bot", "run"],
        cwd=REPO_DIR,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
