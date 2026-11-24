@echo off
rem RUX - Onlyrutsuu. Execute in the current user's project directory.
setlocal
pushd "%~dp0" || exit /b 1
set "PY=.venv\Scripts\python.exe"
if exist "%PY%" goto dependencies
where py >nul 2>nul
if errorlevel 1 goto python_on_path
py -3.12 -m venv .venv
if not errorlevel 1 goto dependencies
:python_on_path
python -m venv .venv
if errorlevel 1 goto failed
:dependencies
"%PY%" -c "import sys,sysconfig; sys.exit(0 if sysconfig.get_platform()=='win-amd64' and (3,11)<=sys.version_info[:2]<(3,15) else 'Python 3.11-3.14 Windows x64 requis (3.12 recommande).')"
if errorlevel 1 goto failed
"%PY%" -m pip install --disable-pip-version-check ".[build]"
if errorlevel 1 goto failed
"%PY%" -m unittest discover -s tests -v
if errorlevel 1 goto failed
"%PY%" -m PyInstaller --clean --noconfirm --workpath ".pyi-work" --distpath "dist" "build\RUX.spec"
if errorlevel 1 goto failed
start "" /wait "dist\RUX.exe" --self-test ".pyi-work\self-test.json"
if errorlevel 1 goto failed
"%PY%" -c "import json,pathlib,sys; sys.exit(0 if json.loads(pathlib.Path('.pyi-work/self-test.json').read_text(encoding='utf-8'))['ok'] else 1)"
if errorlevel 1 goto failed
"%PY%" -c "import hashlib,pathlib; p=pathlib.Path('dist/RUX.exe'); h=hashlib.sha256(p.read_bytes()).hexdigest(); p.with_suffix('.exe.sha256').write_text(h+'  RUX.exe\n',encoding='ascii'); print('SHA-256',h)"
if errorlevel 1 goto failed
echo Build OK: dist\RUX.exe
popd
exit /b 0
:failed
echo Echec du build. Consulte le message ci-dessus.
popd
exit /b 1
