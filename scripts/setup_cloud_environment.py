"""Prepare editable sibling dependencies for Cursor Cloud development."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"

REPOS = {
    "pyPhoCoreHelpers": "https://github.com/CommanderPho/pyPhoCoreHelpers.git",
    "NeuroPy": "https://github.com/CommanderPho/NeuroPy.git",
    "PhoPyLSLhelper": "https://github.com/PhoPersonalOrg/phopylslhelper.git",
    "PhoPyMNEHelper": "https://github.com/PhoPersonalOrg/PhoPyMNEHelper.git",
}


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def ensure_repo(name: str, url: str) -> None:
    target = DEPS / name
    if target.exists():
        run("git", "-C", str(target), "fetch", "--depth", "1", "origin")
        return
    run("git", "clone", "--depth", "1", url, str(target))


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        return
    path.write_text(text.replace(old, new))


def write_file(path: Path, text: str) -> None:
    if path.exists() and path.read_text() == text:
        return
    path.write_text(text)


def patch_numpy_aliases(path: Path) -> None:
    text = path.read_text()
    replacements = {
        "np.float": "np.float64",
        "np.int": "np.int64",
        "np.bool": "np.bool_",
        "np.float6432": "np.float32",
        "np.float6464": "np.float64",
        "np.int648": "np.int8",
        "np.int6416": "np.int16",
        "np.int6432": "np.int32",
        "np.int6464": "np.int64",
        "np.bool__": "np.bool_",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text)


def patch_dependencies() -> None:
    core_pyproject = DEPS / "pyPhoCoreHelpers" / "pyproject.toml"
    replace_once(core_pyproject, '"numpy>=1.23.2,<2"', '"numpy>=1.23.2,<3"')
    replace_once(core_pyproject, '"pandas==1.5.3"', '"pandas>=1.5.3,<3"')
    replace_once(core_pyproject, '"numba>=0.56.4,<0.57"', '"numba>=0.62.1,<0.63"')

    neuropy_pyproject = DEPS / "NeuroPy" / "pyproject.toml"
    replace_once(neuropy_pyproject, 'python-benedict = "^0.28.3"', 'python-benedict = ">=0.35.0,<0.36.0"')
    replace_once(neuropy_pyproject, 'numpy = "^1.20"', 'numpy = ">=1.23.2,<3"')
    replace_once(neuropy_pyproject, 'scipy = "^1.6"', 'scipy = ">=1.13.1,<2"')
    replace_once(neuropy_pyproject, 'pandas = "1.5.3"', 'pandas = ">=1.5.3,<3"')
    replace_once(neuropy_pyproject, 'hmmlearn = "^0.2.8"', 'hmmlearn = ">=0.3.3"')
    replace_once(neuropy_pyproject, 'numba = {version = "^0.56.4", optional = true}', 'numba = {version = ">=0.61.2,<0.63", optional = true}')

    write_file(DEPS / "pyPhoCoreHelpers" / "src" / "nptyping.py", "import numpy as np\n\nNDArray = np.ndarray\nShape = object\n")
    patch_numpy_aliases(DEPS / "NeuroPy" / "neuropy" / "utils" / "ccg.py")


def main() -> None:
    DEPS.mkdir(exist_ok=True)
    for name, url in REPOS.items():
        ensure_repo(name, url)
    patch_dependencies()


if __name__ == "__main__":
    main()
