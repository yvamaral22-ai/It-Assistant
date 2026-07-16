@echo off
setlocal
cd /d "%~dp0\.."
echo [1/7] Verificando o Python...
where python >nul 2>&1 || (echo ERRO: Python nao encontrado no PATH. & exit /b 1)
if not exist ".venv\Scripts\python.exe" (
  echo [2/7] Criando ambiente virtual...
  python -m venv .venv || (echo ERRO: falha ao criar o ambiente virtual. & exit /b 1)
) else (echo [2/7] Ambiente virtual encontrado.)
echo [3/7] Instalando dependencias...
call ".venv\Scripts\activate.bat" || (echo ERRO: falha ao ativar o ambiente virtual. & exit /b 1)
python -m pip install -r requirements.txt || (echo ERRO: falha ao instalar dependencias. & exit /b 1)
if not exist data mkdir data
echo [4/7] Criando backup preventivo...
if exist data\it_assistant.db python scripts\backup_database.py || (echo ERRO: falha ao criar backup. & exit /b 1)
echo [5/7] Aplicando migracoes do banco de dados...
python scripts\initialize_database.py || (echo ERRO: falha ao inicializar o banco. & exit /b 1)
echo [6/7] Verificando usuario master...
python scripts\create_master_user.py --if-missing || (echo ERRO: falha ao configurar o usuario master. & exit /b 1)
echo [7/7] Iniciando em http://127.0.0.1:8000 com recarregamento automatico
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
if errorlevel 1 (echo ERRO: o servidor foi encerrado com falha. & exit /b 1)
endlocal
