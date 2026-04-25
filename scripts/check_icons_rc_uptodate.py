"""Exit with code 1 if Icons.qrc or packaged PNGs are newer than icons_rc.py.

Run from repo root after editing icons: ``uv run python scripts/check_icons_rc_uptodate.py``
Then run ``uv run python scripts/compile_qt_resources.py`` to refresh icons_rc.py.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    icons_dir = root / "pypho_timeline" / "resources" / "icons"
    rc_py = icons_dir / "icons_rc.py"
    qrc = icons_dir / "Icons.qrc"
    if not rc_py.is_file():
        raise SystemExit(f"Missing {rc_py}; run scripts/compile_qt_resources.py")
    sources = [qrc, *icons_dir.glob("LogActivityButton/*.png")]
    newest = max(p.stat().st_mtime for p in sources if p.is_file())
    built = rc_py.stat().st_mtime
    if newest > built:
        raise SystemExit("icons_rc.py is older than Icons.qrc or PNGs; run: uv run python scripts/compile_qt_resources.py")


if __name__ == "__main__":
    main()
