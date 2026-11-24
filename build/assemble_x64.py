"""Assembleur hors Windows de la distribution RUX 1.0. Auteur : Onlyrutsuu.

Prend des binaires Windows déjà construits. Le chemin normal de build sur un
poste Windows reste Build-RUX.cmd. Voir README.md pour les prérequis Linux.
"""
import argparse
import ast
import hashlib
import importlib.util
import marshal
import os
import py_compile
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PureWindowsPath

import lief
import pefile
from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.archive.writers import CArchiveWriter, ZlibArchiveWriter
from PyInstaller.utils.win32.winmanifest import create_application_manifest

ROOT = Path(__file__).resolve().parents[1]


def add_pe_resources(bootloader, work):
    """Reprend les chaînes de la même ressource de version que le build natif."""
    tree = ast.parse((ROOT / "build/version_info.txt").read_text("utf-8"))
    strings = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "StringStruct":
            key, value = (ast.literal_eval(arg) for arg in node.args)
            strings[key] = value
    version = strings["FileVersion"].replace(".", ",")
    values = "\n".join(f'VALUE "{key}", "{value}\\0"' for key, value in strings.items())
    rc = f'''LANGUAGE 12, 1
1 ICON "rux.ico"
1 24 "rux.manifest"
1 VERSIONINFO
 FILEVERSION {version}
 PRODUCTVERSION {version}
 FILEFLAGSMASK 0x3f
 FILEFLAGS 0
 FILEOS 0x40004
 FILETYPE 1
BEGIN
 BLOCK "StringFileInfo" BEGIN
  BLOCK "040c04b0" BEGIN
   {values}
  END
 END
 BLOCK "VarFileInfo" BEGIN
  VALUE "Translation", 0x040c, 1200
 END
END
'''
    shutil.copyfile(ROOT / "data/rux.ico", work / "rux.ico")
    (work / "rux.manifest").write_bytes(create_application_manifest())
    (work / "rux.rc").write_text(rc, encoding="utf-8")
    subprocess.run(["x86_64-w64-mingw32-windres", "--preprocessor=cpp", "--preprocessor-arg=-E",
                    "--codepage=65001", "-i", "rux.rc", "-o", "rux.o"], cwd=work, check=True)
    subprocess.run(["x86_64-w64-mingw32-ld", "-shared", "--entry=0", "rux.o", "-o", "res.dll"],
                   cwd=work, check=True)
    resource_dll = lief.PE.parse(str(work / "res.dll"))
    boot = lief.PE.parse(str(bootloader))
    boot.set_resources(resource_dll.resources)
    options = lief.PE.Builder.config_t()
    options.resources = True
    boot.write(str(work / "rux-stub.exe"), options)
    return work / "rux-stub.exe"


def standard_library(source, archive):
    # Preserve the Windows standard library, including platform-specific modules
    # that a dependency scan on a Linux host would miss. Store pyc files at the
    # canonical zipimport path. ZIP_STORED works during interpreter bootstrap.
    skip = {"site-packages", "test", "tests", "__pycache__", "idlelib", "tkinter",
            "turtledemo", "ensurepip", "venv", "lib2to3"}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as out:
        for file in sorted(source.rglob("*.py")):
            rel = file.relative_to(source)
            if skip.intersection(rel.parts):
                continue
            code = compile(file.read_bytes(), str(PureWindowsPath(rel)), "exec", dont_inherit=True)
            header = importlib.util.MAGIC_NUMBER + bytes(12)  # timestamp PYC; no source in archive
            out.writestr(rel.with_suffix(".pyc").as_posix(), header + marshal.dumps(code))


def collect_python_packages(pyi, work):
    """PYZ de l’application et des hooks officiels. Les modules Qt binaires restent sur disque."""
    modules = {}
    entries = []
    roots = [ROOT / name for name in ("core", "agents", "gui", "skills")]
    roots.append(pyi / "fake-modules/_pyi_rth_utils")
    for folder in roots:
        for src in sorted(folder.rglob("*.py")):
            rel = src.relative_to(folder.parent).with_suffix("")
            parts = rel.parts[:-1] if rel.name == "__init__" else rel.parts
            name = ".".join(parts)
            entries.append((name, str(src), "PYMODULE"))
            modules[name] = compile(src.read_bytes(), str(rel) + ".py", "exec", dont_inherit=True)
    ZlibArchiveWriter(str(work / "PYZ.pyz"), entries, modules)
    files = []
    for src in sorted((pyi / "loader").glob("pyimod*.py")):
        bytecode = work / (src.stem + ".pyc")
        py_compile.compile(str(src), cfile=str(bytecode), dfile=src.name, doraise=True)
        files.append((src.stem, str(bytecode), True, "m"))
    files.extend([
        ("pyiboot01_bootstrap", str(pyi / "loader/pyiboot01_bootstrap.py"), True, "s"),
        ("pyi_rth_pyside6", str(pyi / "hooks/rthooks/pyi_rth_pyside6.py"), True, "s"),
        ("main", str(ROOT / "main.py"), True, "s"),
        ("PYZ.pyz", str(work / "PYZ.pyz"), False, "z"),
    ])
    return files


def collect_files(runtime, work):
    packages = runtime / "Lib/site-packages"
    qt = packages / "PySide6"
    pyi = packages / "PyInstaller"
    files = {}

    def add(name, src):
        if not src.is_file():
            raise FileNotFoundError(src)
        files[str(PureWindowsPath(name))] = src

    standard_library(runtime / "Lib", work / "base_library.zip")
    add("base_library.zip", work / "base_library.zip")
    for name in ("python312.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        add(name, runtime / name)
    add("data/distributions/cpython/LICENSE.txt", runtime / "LICENSE.txt")
    for f in (runtime / "DLLs").iterdir():
        if f.suffix.lower() in {".pyd", ".dll"} and not f.name.startswith(("_test", "_tkinter", "tcl", "tk8")):
            add(f.name, f)
    for package in ("PySide6", "shiboken6"):
        folder = packages / package
        for f in folder.glob("*.py"):
            add(Path(package) / f.name, f)
        for f in (folder / "support").rglob("*.py"):
            add(Path(package) / f.relative_to(folder), f)
        for f in folder.glob("*.dll"):
            if f.name.lower().startswith(("msvcp", "vcruntime", "concrt", "shiboken6.", "pyside6.abi3")):
                add(Path(package) / f.name, f)
    for name in ("QtCore.pyd", "QtGui.pyd", "QtWidgets.pyd", "Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll",
                 "plugins/platforms/qwindows.dll", "plugins/platforms/qoffscreen.dll",
                 "plugins/imageformats/qico.dll", "translations/qtbase_fr.qm"):
        add(Path("PySide6") / name, qt / name)
    add("shiboken6/Shiboken.pyd", packages / "shiboken6/Shiboken.pyd")
    for name in ("oui.csv", "rux.ico", "NOTICE.txt"):
        add(Path("data") / name, ROOT / "data" / name)
    for f in (ROOT / "data/licenses").glob("*.txt"):
        add(Path("data/licenses") / f.name, f)
    for pattern in ("pyside6_essentials-*.dist-info", "shiboken6-*.dist-info", "pyinstaller-*.dist-info"):
        info, = packages.glob(pattern)
        for f in info.rglob("*"):
            rel = f.relative_to(info)
            if f.is_file() and ("licenses" in rel.parts or f.name.upper().startswith(("COPYING", "LICENSE", "NOTICE"))):
                add(Path("data/distributions") / info.name / rel, f)
    entries = collect_python_packages(pyi, work)
    for name, src in sorted(files.items()):
        entries.append((name, str(src), True, "b" if src.suffix.lower() in {".pyd", ".dll"} else "x"))
    return pyi, entries


def assemble(runtime: Path, output: Path):
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Utilise CPython 3.12 pour produire le bytecode de CPython 3.12.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rux-package-", dir=output.parent) as temporary:
        work = Path(temporary)
        pyi, entries = collect_files(runtime, work)
        stub = add_pe_resources(pyi / "bootloader/Windows-64bit-intel/runw.exe", work)
        archive = work / "rux.pkg"
        CArchiveWriter(str(archive), entries, "python312.dll")
        result = work / "RUX.exe"
        with result.open("wb") as out:
            for f in (stub, archive):
                with f.open("rb") as part:
                    shutil.copyfileobj(part, out)
        pe = pefile.PE(str(result), fast_load=True)
        if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Subsystem != 2:
            raise RuntimeError("Format de l’exécutable inattendu.")
        check = pe.generate_checksum()
        offset = pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
        pe.close()
        with result.open("r+b") as out:
            out.seek(offset)
            out.write(struct.pack("<I", check))
        reader = CArchiveReader(str(result))
        for name, src, compressed, kind in entries:
            content = reader.extract(name)
            if kind in {"b", "x", "z"} and content != Path(src).read_bytes():
                raise RuntimeError(f"Contenu de l’archive différent pour {name}")
        os.replace(result, output)
    print(output, hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path, help="CPython Windows x64 avec les wheels installées")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    assemble(args.runtime.resolve(), args.output.resolve())
