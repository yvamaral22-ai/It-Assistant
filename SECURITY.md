# Segurança do IT Self-Service Assistant

Este projeto trata dados de atendimento interno. A regra base é simples: o front-end pode melhorar a experiência, mas nunca pode ser a camada que protege dados ou decide permissões.

## Checklist obrigatório por feature

Antes de considerar uma feature pronta, responda:

- A feature manipula dado pessoal, máquina, setor, localidade, histórico ou relatório?
- O endpoint precisa de autenticação?
- O endpoint precisa de autorização por papel?
- O endpoint público precisa de rate limit?
- O backend valida tamanho, tipo e conteúdo do input?
- A mesma ação foi testada via requisição direta, sem depender da tela?
- A resposta retorna só o mínimo necessário?
- Logs e auditoria evitam senha, token, cookie e dados pessoais desnecessários?
- Existe teste automatizado cobrindo acesso permitido e negado?
- A mudança passa no `scripts\security_check.ps1`?

## Matriz de permissões

| Papel | Sessões | Relatórios | Exportar CSV | Base de conhecimento | Avisos | Processos | Usuários | Auditoria |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `master` | sim | sim | sim | sim | sim | sim | sim | sim |
| `analyst` | sim | sim | sim | não | leitura | não | não | não |
| `editor` | não | não | não | sim | sim | não | não | não |
| `reader` | sim | sim | não | não | não | não | não | não |

Mudanças nessa matriz exigem alteração em `app/services/access_control.py` e testes correspondentes.

## Comando padrão antes de publicar

Execute na raiz do projeto:

```powershell
.\scripts\security_check.ps1
```

Esse script roda:

- testes automatizados;
- Ruff;
- checagem de sintaxe JavaScript;
- varredura local de segredos;
- auditoria de dependências.

## Regras de front-end

- Nunca colocar `SECRET_KEY`, token, senha, connection string ou chave de serviço no front-end.
- Nunca confiar no front-end para esconder dados sensíveis.
- Nunca depender de botão desabilitado, rota escondida ou componente invisível como controle de segurança.
- Dados vindos do usuário devem ser exibidos escapados.

## Regras de backend

- Toda permissão deve ser validada no backend.
- Toda escrita administrativa deve exigir CSRF.
- Toda API pública de escrita deve ter rate limit.
- Dados dinâmicos com histórico, relatório, ticket, pessoa ou máquina devem usar `Cache-Control: no-store`.
- Exportações CSV devem proteger contra fórmulas de planilha.

## Produção

Produção exige:

- `APP_ENV=production`;
- `APP_DEBUG=false`;
- `SECRET_KEY` forte;
- `PUBLIC_BASE_URL` com HTTPS;
- `ALLOWED_HOSTS` restrito ao DNS/IP oficial;
- PostgreSQL; SQLite é apenas para piloto local;
- IIS/reverse proxy na frente do Uvicorn;
- porta 8000 acessível somente localmente pelo proxy;
- permissões restritas em `.env`, `data/`, backups e logs;
- backup protegido e restauração testada.

Para múltiplos servidores, não escale enquanto houver estado local compartilhado em arquivo. Primeiro migre para PostgreSQL e centralize rate limit, logs e estado operacional.
