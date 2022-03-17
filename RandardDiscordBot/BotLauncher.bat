cd %~dp0\..
set PYTHONPATH=%cd%;%PYTHONPATH%
call venv\Scripts\activate.bat
cd RandardDiscordBot
py -i BotMain.py