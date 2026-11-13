@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Первый запуск: создаю окружение и ставлю зависимости, это займёт минуту...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo Не найден Python 3.11+. Установите его с https://www.python.org/downloads/ и запустите снова.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Не удалось установить зависимости. Проверьте интернет и запустите снова.
  pause
  exit /b 1
)
echo trainwatch запускается: интерфейс откроется в браузере. Не закрывайте это окно.
".venv\Scripts\python.exe" -m trainwatch run
pause
