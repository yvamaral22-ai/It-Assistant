@echo off
set APP_ENV=development
cd /d "%~dp0\.."
call ".venv\Scripts\activate.bat"
echo AVISO: modo de rede para piloto HTTP. Para producao, use run_server_production.bat atras do IIS/HTTPS.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-server-header --limit-concurrency 100 --timeout-keep-alive 5
