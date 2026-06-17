@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo NovelBuddy 启动中...
start http://127.0.0.1:8765/
uv run python -m novelbuddy.web --port 8765
