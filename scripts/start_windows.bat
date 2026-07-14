@echo off
setlocal
cd /d "%~dp0\.."
echo [1/5] Verificando o Python...
where python >nul 2>&1 || (echo ERRO: Python nao encontrado no PATH. & exit /b 1)
if not exist ".venv\Scripts\python.exe" (
  echo [2/5] Criando ambiente virtual...
  python -m venv .venv || (echo ERRO: falha ao criar o ambiente virtual. & exit /b 1)
) else (echo [2/5] Ambiente virtual encontrado.)
echo [3/5] Instalando dependencias...
call ".venv\Scripts\activate.bat" || (echo ERRO: falha ao ativar o ambiente virtual. & exit /b 1)
python -m pip install -r requirements.txt || (echo ERRO: falha ao instalar dependencias. & exit /b 1)
if not exist data mkdir data
echo [4/5] Inicializando banco de dados...
python scripts\initialize_database.py || (echo ERRO: falha ao inicializar o banco. & exit /b 1)
echo [5/5] Iniciando em http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if errorlevel 1 (echo ERRO: o servidor foi encerrado com falha. & exit /b 1)
endlocal

