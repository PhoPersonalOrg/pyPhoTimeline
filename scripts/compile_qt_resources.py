"""Regenerate pypho_timeline/resources/icons/icons_rc.py from Icons.qrc.

Uses pyrcc6 when available on PATH; otherwise pyrcc5 from the same venv as this
interpreter, then rewrites the import to PyQt6 (resource blobs are compatible).
Run from repo root: ``uv run python scripts/compile_qt_resources.py``
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _scripts_dir() -> Path:
    return Path(sys.executable).resolve().parent


def _find_rcc_exe() -> str | None:
    bindir = _scripts_dir()
    for name in ("pyrcc6", "pyrcc6.exe", "pyrcc5", "pyrcc5.exe"):
        p = bindir / name
        if p.is_file():
            return str(p)
    return None


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    qrc = root / "pypho_timeline" / "resources" / "icons" / "Icons.qrc"
    out = root / "pypho_timeline" / "resources" / "icons" / "icons_rc.py"
    if not qrc.is_file():
        raise SystemExit(f"Missing {qrc}")
    rcc = _find_rcc_exe()
    if rcc is None:
        raise SystemExit("No pyrcc6 or pyrcc5 found next to the current Python (install pyqt6-tools / pyqt5-tools).")
    tmp = out.with_suffix(".py.tmp")
    subprocess.run([rcc, str(qrc), "-o", str(tmp)], cwd=str(root), check=True)
    text = tmp.read_text(encoding="utf-8")
    if "pyrcc5" in Path(rcc).name.lower():
        text = text.replace("from PyQt5 import QtCore", "from PyQt6 import QtCore", 1)
        text = text.replace("The Resource Compiler for PyQt5 (Qt v5.15.2)", "The Resource Compiler for PyQt5 (Qt v5.15.2), import line changed to PyQt6 for runtime compatibility", 1)
    out.write_text(text, encoding="utf-8")
    tmp.unlink(missing_ok=True)
    print(f"Wrote {out.relative_to(root)}")


if __name__ == "__main__":
    main()
