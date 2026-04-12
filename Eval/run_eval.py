"""Shim: run from repo root with SRC on path. Prefer: cd SRC && uv run python -m eval_harness.run_eval"""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "SRC"
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(src))
    cmd = [sys.executable, "-m", "eval_harness.run_eval", *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, cwd=src, env=env))


if __name__ == "__main__":
    main()
