# IT Self-Service Assistant

Sistema interno de autoatendimento de TI. Conduz o usuário por perguntas em JSON, apresenta até três orientações seguras, registra o resultado e prepara um resumo para o suporte ou futura integração GLPI.

## Funcionalidades

- Sete categorias: Excel, Outlook, navegador, impressora, Windows, rede e outros.
- Diagnóstico de uma pergunta por vez, retorno seguro e retomada de sessão.
- Busca de categoria, impressão, resumo copiável e avaliação de 1 a 5.
- Dados estruturados de localidade e tipo de problema.
- Histórico protegido e relatórios com filtros e CSV.
- Avisos internos publicados na página inicial sem interromper o autoatendimento.
- Processos internos em abas verticais, com tópicos editáveis exclusivamente pelo master.
- Eficácia por solução, resolução por tentativa, tempo médio, recorrência e satisfação.
- Papéis `master`, `analyst`, `editor` e `reader`.
- Rascunho, publicação, comparação, restauração e auditoria dos fluxos JSON.
- Backup preventivo, logs rotativos, manutenção e endpoints de prontidão.
- Clientes desabilitados e preparados para GLPI, Active Directory e Microsoft Graph.

## Tecnologias

Python 3.12 ou superior compatível, FastAPI, Uvicorn, SQLAlchemy 2, Alembic, SQLite/PostgreSQL, Pydantic, Jinja2, HTML, CSS e JavaScript puro. Não há dependências de frontend por CDN.

## Instalação no Windows

Pré-requisito: Python no `PATH`. Execute:

```bat
cd /d X:\It-Assistant
scripts\start_windows.bat
```

O script cria o ambiente virtual, instala dependências, faz backup preventivo, aplica migrações, verifica o master e inicia em <http://127.0.0.1:8000>. Na primeira execução, guarde a senha master exibida.

Instalação manual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts\initialize_database.py
python scripts\create_master_user.py --if-missing
python run.py
```

Para redefinir o master localmente:

```powershell
.\.venv\Scripts\python.exe scripts\create_master_user.py --username master
```

## Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app scripts tests migrations
.\.venv\Scripts\python.exe scripts\audit_dependencies.py
```

Os testes usam SQLite temporário e validam regras, segurança, relatórios, versionamento e migrações.

## Usuários e permissões

- `master`: acesso total, usuários, auditoria, processos internos, conteúdo, histórico e relatórios.
- `analyst`: histórico, relatórios, exportação e consulta dos avisos internos.
- `editor`: edição da base de conhecimento e dos avisos internos.
- `reader`: histórico e relatórios sem exportação.

O master gerencia acessos em `/admin/control/users`. O último master ativo não pode ser removido. Credenciais são armazenadas somente como hash `scrypt` com salt; nunca use a senha corporativa.

## Base de conhecimento

As categorias ficam em `app/knowledge_base`. O painel `/admin/control` cria versões no banco. Salvar gera um rascunho validado; publicar troca o JSON ativo e preserva a versão anterior.

Cada arquivo contém `category`, `title`, `start_node` e `nodes`. Nós podem ser `question`, `solution` ou `end`. Perguntas exigem opções com `label`, `value` e `next`. Soluções usam `title`, `text`, `steps`, `ask_if_resolved` e opcionalmente `unresolved_next`, `media` e `media_alt`.

A validação rejeita JSON inválido, início ou destino inexistente, pergunta sem opções, tipo inválido e ciclos alcançáveis.

## Banco, backup e operação

Alembic aplica migrações automaticamente. Comandos úteis:

```powershell
.\.venv\Scripts\python.exe scripts\initialize_database.py
.\.venv\Scripts\python.exe scripts\backup_database.py
.\.venv\Scripts\python.exe -m alembic current
```

Backups SQLite ficam em `data/backups`; logs rotativos, em `data/logs/application.log`. `/health` confirma o processo e `/ready` testa banco e conhecimento. `MAINTENANCE_MODE=true` ativa a página de manutenção após reinício.

Para PostgreSQL, configure:

```env
DATABASE_URL=postgresql+psycopg://usuario:senha@servidor/banco
```

Consulte `deployment/README.md` para inicialização automática, backup diário, IIS, HTTPS e DNS interno.

## Segurança

- Administração, histórico, relatórios e exportações exigem autenticação e permissão.
- Formulários administrativos usam CSRF, cookie assinado e limitação de login.
- Cada diagnóstico fica vinculado à sessão assinada do navegador; conhecer outro UUID não concede acesso ao atendimento.
- As APIs públicas retornam somente o estado mínimo necessário e não devolvem identificação, máquina ou descrição.
- Respostas usam CSP, proteção contra framing e MIME sniffing, política de origem, `no-store` para dados dinâmicos e hosts permitidos.
- Alterações de senha ou papel invalidam sessões administrativas antigas.
- A auditoria não registra senhas.
- CSV é protegido contra fórmulas de planilha.
- O diagnóstico não solicita senha, não executa comandos e não aceita código do navegador.
- Em produção, configure `APP_ENV=production`, `APP_DEBUG=false`, `SECRET_KEY` forte, `ALLOWED_HOSTS`, `PUBLIC_BASE_URL` HTTPS e use `scripts\run_server_production.bat` atrás do IIS.

## Limitações

- SQLite é adequado para piloto e baixo volume; use PostgreSQL para concorrência corporativa.
- GLPI, AD e Microsoft Graph ainda não realizam chamadas reais.
- DNS, certificado e regras de firewall dependem da infraestrutura da empresa.
- Não há execução remota, upload, agente local ou inteligência artificial.

## Rotas principais

Públicas: `/`, `/health`, `/ready`, `/diagnostic/{category}` e API de sessões. Protegidas: `/admin/sessions`, `/admin/reports`, `/admin/control`, usuários, auditoria e versionamento de conhecimento.
