"""Optional: render eval reports from JSON output of eval_harness.run_eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not path or not path.exists():
        print("Usage: python report.py <eval_output.json>")
        raise SystemExit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    print("Classifier eval summary")
    print("------------------------")
    for k, v in data.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
