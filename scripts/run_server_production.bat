@echo off
setlocal
set APP_ENV=production
cd /d "%~dp0\.."
call ".venv\Scripts\activate.bat" || (echo ERRO: ambiente virtual indisponivel. & exit /b 1)
if not exist ".env" (echo ERRO: crie e proteja o arquivo .env antes de iniciar em producao. & exit /b 1)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-server-header --limit-concurrency 100 --timeout-keep-alive 5
if errorlevel 1 (echo ERRO: o servidor de producao foi encerrado com falha. & exit /b 1)
endlocal
