@echo off
rem ============================================================
rem  Update Log viewer (deployed by tools/build.py)
rem  - UPDATES.txt is regenerated on every build from CHANGELOG.md
rem  - This .bat is ASCII-only on purpose (codepage-safe logic);
rem    the Chinese content is displayed via chcp 65001 + type.
rem ============================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist "UPDATES.txt" (
  echo [!] UPDATES.txt not found next to this launcher.
  echo     Run tools/build.py to regenerate the release bundle.
  pause
  exit /b 1
)
type "UPDATES.txt"
echo.
echo ------------------------------------------------------------
pause
endlocal
