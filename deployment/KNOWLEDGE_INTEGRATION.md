# Integração da base de conhecimento

## Estado atual

O relato informado na abertura é comparado somente com regras locais versionadas em `app/knowledge_base`. A regra registra uma classificação e um nível de confiança no banco, sem devolver o texto sensível do usuário ao navegador.

- Confiança alta: inicia na pergunta de confirmação associada à regra.
- Confiança média ou baixa: mantém o início padrão da categoria.
- O destino de uma regra deve ser uma pergunta; nunca uma solução.
- A solução continua dependendo das respostas confirmadas pelo usuário.
- Se a primeira orientação não resolver, o fluxo oferece até três tentativas antes de gerar o resumo.
- Os relatórios agregam as classificações, sem expor os relatos completos.

Exemplo:

```json
{
  "id": "excel_file_problem",
  "label": "Falha ao abrir uma planilha",
  "target_node": "excel_002",
  "keywords": ["planilha não abre", "arquivo corrompido"]
}
```

## Próxima etapa: GLPI

O GLPI deve continuar como fonte oficial. O aplicativo deve sincronizar, em modo somente leitura, apenas artigos publicados e autorizados para o público interno, mantendo uma cópia local indexada para velocidade e indisponibilidade temporária.

Antes da implementação será necessário confirmar a versão do GLPI e o modo de API disponível. Para a API V2, a preferência é OAuth2 com uma aplicação de escopo mínimo. Tokens, segredos e credenciais ficam exclusivamente no servidor e nunca são enviados ao frontend.

O sincronizador deverá guardar ao menos:

- identificador e versão do artigo no GLPI;
- título, conteúdo sanitizado, categoria e público autorizado;
- data da última atualização e estado de publicação;
- referência da fonte exibida junto à orientação;
- hash do conteúdo para atualização incremental.

## Etapa posterior: IA controlada

A IA poderá interpretar linguagem livre e ordenar artigos candidatos, mas não será a fonte da solução. O contexto enviado deve ser minimizado e anonimizado. A resposta final deve usar somente conteúdo aprovado, informar a fonte e retornar ao fluxo de perguntas quando a confiança não for suficiente.

Regras de segurança:

- não enviar nome, computador, setor ou localidade ao modelo sem necessidade explícita;
- não permitir que o modelo execute comandos, altere o GLPI ou encerre o atendimento;
- tratar artigos e relatos como dados não confiáveis contra injeção de instruções;
- validar a saída no backend e manter limites de confiança;
- registrar artigo, versão, classificação e resultado para auditoria;
- oferecer uma saída segura quando não houver correspondência confiável.
