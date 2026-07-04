@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ========================================
echo   GitHub 업로드
echo ========================================
echo.
echo GitHub 토큰(ghp_...)을 붙여넣고 Enter를 누르세요.
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0push-to-github.ps1"
echo.
pause
