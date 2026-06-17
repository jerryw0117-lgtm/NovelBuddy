@echo off
chcp 65001 >nul
echo 正在停止 NovelBuddy...
taskkill /f /im python.exe /fi "WINDOWTITLE eq *novelbuddy*" >nul 2>&1
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /v /fo list ^| findstr "novelbuddy"') do taskkill /f /pid %%a >nul 2>&1
echo NovelBuddy 已停止
pause
