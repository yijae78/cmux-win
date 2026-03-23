@echo off
REM cmux-win codex wrapper — passthrough to real codex with env injection
REM If CMUX_SURFACE_ID is set, we're inside cmux-win terminal

IF NOT DEFINED CMUX_SURFACE_ID (
  codex.exe %*
  exit /b %ERRORLEVEL%
)

REM Find real codex.exe (skip this wrapper)
for /f "tokens=*" %%i in ('where codex.exe 2^>nul') do (
  set "CODEX_PATH=%%i"
  if /i not "%%~dpi"=="%~dp0" (
    "%%i" %*
    exit /b %ERRORLEVEL%
  )
)

echo [cmux-win] codex not found in PATH
exit /b 1
