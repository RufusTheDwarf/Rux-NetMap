# -*- mode: python ; coding: utf-8 -*-
# RUX — Onlyrutsuu
import sys
from importlib.metadata import distribution
from pathlib import Path

root = Path(SPECPATH).resolve().parent
assets = [(str(root / "data" / name), "data")
          for name in ("oui.csv", "NOTICE.txt", "rux.ico")]
assets.append((str(root / "data" / "licenses"), "data/licenses"))
for package in ("PySide6-Essentials", "shiboken6", "pyinstaller"):
    dist = distribution(package)
    for item in dist.files or ():
        if not any(part.endswith(".dist-info") for part in item.parts):
            continue
        if item.name.lower().startswith(("license", "copying", "notice")) or "licenses" in item.parts:
            src = Path(dist.locate_file(item))
            if src.is_file():
                # Preserve the path so third-party notices with identical names survive.
                dest = Path("data/distributions") / package / Path(str(item)).parent
                assets.append((str(src), str(dest)))
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    assets.append((str(python_license), "data/distributions/cpython"))

a = Analysis([str(root / "main.py")], pathex=[str(root)], datas=assets,
             binaries=[], hiddenimports=[], hookspath=[], runtime_hooks=[],
             excludes=["PyQt5", "PyQt6", "PySide2", "tkinter"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="RUX", console=False,
          debug=False, strip=False, upx=False, uac_admin=False,
          icon=str(root / "data" / "rux.ico"),
          version=str(root / "build" / "version_info.txt"))
