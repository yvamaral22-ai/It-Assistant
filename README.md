# IT Self-Service Assistant

MVP local de autoatendimento de TI. O sistema conduz o usuário por perguntas armazenadas em JSON, apresenta orientações seguras e registra um resumo para encaminhamento futuro ao suporte ou GLPI.

## Funcionalidades

- Página inicial responsiva com identificação opcional e sete categorias.
- Diagnóstico de uma pergunta por vez, controlado por grafos JSON validados.
- Orientações para Excel, Outlook, navegador, impressora, Windows, rede e outros problemas.
- Registro de sessões e interações em SQLite.
- Até três tentativas de solução antes do encerramento como não resolvido.
- Retorno seguro à pergunta anterior para alterar uma resposta.
- Encerramento como resolvido, não resolvido ou abandonado.
- Resumo técnico copiável para a área de transferência.
- Histórico local em `/admin/sessions`.
- Relatórios operacionais em `/admin/reports`, com filtros, indicadores, rankings e exportação CSV.
- Clientes preparados, porém desabilitados, para GLPI, Active Directory e Microsoft Graph.

## Tecnologias e estrutura

Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2, SQLite, Pydantic, Jinja2, HTML, CSS e JavaScript puro. `app/api` contém HTTP; `services` contém regras de negócio; `repositories` isola banco e JSON; `models` e `schemas` definem dados; `integrations` contém stubs; `templates` e `static` formam a interface; `knowledge_base` guarda os fluxos; `tests` usa banco temporário.

## Instalação rápida no Windows

Pré-requisitos: Python 3.12 (ou versão estável compatível) disponível no `PATH` e acesso à internet apenas na primeira instalação das dependências.

```bat
git clone <endereco-do-repositorio>
cd It-Assistant
scripts\start_windows.bat
```

Depois, acesse <http://127.0.0.1:8000>. Após instalar as dependências, a aplicação funciona sem internet.

Instalação manual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts\initialize_database.py
python run.py
```

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes usam SQLite temporário e não alteram `data/it_assistant.db`.

## Base de conhecimento

Para adicionar uma categoria:

1. Inclua nome, `slug`, ícone e descrição em `app/knowledge_base/categories.json`.
2. Crie `app/knowledge_base/<slug>.json` com `category`, `title`, `start_node` e `nodes`.
3. Use nós `question`, `solution` ou `end`. Perguntas exigem `options`; cada opção exige `label`, `value` e `next`.
4. Em soluções, use `title`, `text`, `steps` e `ask_if_resolved`. Um `next` opcional pode continuar o fluxo.
5. Execute os testes. A validação rejeita início ou destinos inexistentes, perguntas sem opções, tipos inválidos, JSON corrompido e ciclos alcançáveis.

Exemplo mínimo:

```json
{"category":"exemplo","title":"Exemplo","start_node":"q1","nodes":{"q1":{"type":"question","text":"Funcionou?","options":[{"label":"Não","value":"no","next":"s1"}]},"s1":{"type":"solution","title":"Orientação","text":"Faça um teste seguro.","steps":["Passo 1"],"ask_if_resolved":true}}}
```

## Histórico e segurança

O histórico fica em <http://127.0.0.1:8000/admin/sessions> e os relatórios em <http://127.0.0.1:8000/admin/reports>. **Os painéis administrativos não possuem autenticação neste MVP e jamais devem ser expostos em produção.** Antes de publicar, implemente autenticação corporativa, autorização por perfil, HTTPS, CSRF para formulários administrativos, retenção e auditoria.

O sistema não solicita nem armazena senhas, não executa comandos enviados pelo navegador e usa ORM. Não registre segredos na descrição. Copie `.env.example` somente se precisar alterar configurações e troque `SECRET_KEY` antes de qualquer implantação; não versione `.env`.

## Limitações e próximos passos

- Sem autenticação, upload, execução remota, IA ou integração externa real.
- “Voltar” altera somente a tela; respostas já registradas permanecem no histórico para auditoria.
- SQLite atende uso local e de baixo volume, não implantação corporativa concorrente.
- O resumo é copiado; nenhum ticket é aberto automaticamente.

Próximas etapas recomendadas: autenticação e autorização; migrações com Alembic; PostgreSQL; proteção CSRF e política de retenção; testes E2E e acessibilidade; então implementar GLPI com cofre de segredos e conta técnica. Active Directory exigirá conta de serviço, privilégio mínimo, autorização e auditoria; Microsoft Graph exigirá registro de aplicativo, permissões mínimas e autenticação segura. Nenhuma ação administrativa deve ser adicionada sem aprovação formal.

## Rotas

`GET /`, `/health`, `/diagnostic/{category}`, `/admin/sessions`, `/admin/sessions/{id}`; `POST /api/sessions`, `POST /api/sessions/{id}/answer`, `POST /api/sessions/{id}/finish`; `GET /api/sessions/{id}` e `/api/sessions/{id}/summary`.




http://127.0.0.1:8000/