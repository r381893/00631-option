@echo off
chcp 65001 >nul
echo ========================================
echo   啟動 00631L 避險計算器
echo ========================================
echo.
cd /d "%~dp0"
echo 正在啟動應用程式...
echo 請在瀏覽器中開啟: http://localhost:8501
echo.
streamlit run app.py
pause
