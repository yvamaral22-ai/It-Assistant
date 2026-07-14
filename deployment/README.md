# Publicação interna

## Arquitetura recomendada

`Usuários → DNS interno + HTTPS/IIS → Uvicorn em 127.0.0.1:8000 → PostgreSQL`

O arquivo `iis/web.config.example` é uma referência para URL Rewrite + ARR. A infraestrutura deve emitir o certificado interno, criar o DNS e restringir firewall conforme as políticas da empresa.

## Preparação

1. Use uma VM ou servidor Windows dedicado e uma conta de serviço sem login interativo.
2. Copie `.env.example` para `.env`, defina `APP_ENV=production`, uma `SECRET_KEY` forte e a `DATABASE_URL`.
3. Para PostgreSQL, use `DATABASE_URL=postgresql+psycopg://usuario:senha@servidor/banco` e guarde o segredo no mecanismo aprovado pela empresa.
4. Execute `scripts\start_windows.bat` uma vez para instalar dependências e migrar o banco.
5. Instale a inicialização automática com `powershell -ExecutionPolicy Bypass -File scripts\install_startup_task.ps1`.
6. Instale o backup diário com `powershell -ExecutionPolicy Bypass -File scripts\install_backup_task.ps1` (para PostgreSQL, substitua pelo `pg_dump` corporativo).
7. Configure IIS/HTTPS e encaminhe somente para `127.0.0.1:8000`.
8. Monitore `/health` (processo) e `/ready` (banco e conhecimento).

## Manutenção

Defina `MAINTENANCE_MODE=true` e reinicie para exibir uma página de manutenção aos usuários. Administração, arquivos estáticos e endpoints de monitoramento permanecem disponíveis.

## Recuperação

Os backups SQLite ficam em `data/backups` e usam a API de backup consistente do SQLite. Teste a restauração periodicamente em outra pasta. Nunca considere um backup confiável sem um teste de restauração.
