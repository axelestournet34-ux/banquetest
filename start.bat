@echo off
title Budget Mensuel
echo.
echo  ====================================
echo   Budget Mensuel - Demarrage...
echo  ====================================
echo.

REM Installe les dependances si necessaire
pip install -r requirements.txt --quiet

echo  [1/2] Demarrage du serveur Revolut (port 8000)...
start "Webhook Revolut" /min cmd /c "uvicorn webhook:app --host 0.0.0.0 --port 8000"

timeout /t 2 /nobreak >nul

echo  [2/2] Demarrage de l'application budget...
echo.
echo  Ouvrez votre telephone et allez sur :
echo  http://[IP de votre PC]:8501
echo.
start "App Budget" cmd /c "streamlit run app.py --server.port 8501 --server.address 0.0.0.0"

timeout /t 3 /nobreak >nul
echo  Application demarree ! Appuyez sur une touche pour arreter.
pause >nul

taskkill /fi "WINDOWTITLE eq Webhook Revolut*" /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq App Budget*" /f >nul 2>&1
