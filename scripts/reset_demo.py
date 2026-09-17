"""Clear the queue and the saved corrections, so a demo starts from zero.

    uv run python scripts/reset_demo.py

Use before recording, and before deploying, so the app does not open with test
data in the sidebar. Does not touch knowledge/profile.yaml.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "data" / "pending_questions.json",
    ROOT / "data" / "corrections.json",
]


def main() -> int:
    removed = 0
    for path in TARGETS:
        if path.exists():
            path.unlink()
            print(f"removed {path.relative_to(ROOT)}")
            removed += 1

    if not removed:
        print("Already clean, nothing to remove.")

    print("\nThe app recreates these files on the next run.")
    print("If the app is running, restart it so the sidebar refreshes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
