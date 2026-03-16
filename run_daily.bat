@echo off
chcp 65001 >nul
cd /d "%~dp0"
python send_daily_exec_news.py
rem 오류 시에만 종료 코드로 알림 (작업 스케줄러용으로 pause 없음)
