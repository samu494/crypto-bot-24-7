@echo off
echo ========================================
echo    Crypto Daily Telegram Bot
echo ========================================
echo.

cd /d "%~dp0"

if not exist "venv" (
    echo Creation de l'environnement virtuel...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installation des dependances...
pip install -r requirements.txt -q

echo.
if not exist ".env" (
    echo Fichier .env non trouve!
    echo Copie .env.example en .env et remplis ton token.
    pause
    exit /b 1
)

echo Demarrage du bot...
python bot.py
pause
