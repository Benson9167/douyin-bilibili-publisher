@echo off
REM 复制并替换 <ACCOUNT_NAME> 与路径为本地实际路径，切勿将真实账号脚本提交至 Git
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="%~dp0..\profiles\<ACCOUNT_NAME>" --no-first-run --no-default-browser-check "https://creator.douyin.com/creator-micro/content/upload" "https://member.bilibili.com/platform/upload/video/frame"
