# API rafaau

Serviço FastAPI separado do aplicativo desktop. Ele mantém contas, licenças, dispositivos, cotas, assinaturas e o estado temporário do OAuth do Trello. Também intermedeia a seleção de cortes pela OpenAI. Clientes e conteúdos editoriais não são sincronizados aqui: permanecem no SQLite local do desktop.

## Configuração

Variáveis de produção:

- `DATABASE_URL`: PostgreSQL. Sem ela, a API usa `sqlite:///./neiva_ai.db`, adequado somente a desenvolvimento/teste.
- `OPENAI_API_KEY`: chave usada exclusivamente no servidor.
- `OPENAI_MODEL`: opcional; padrão `gpt-5-mini`.
- `NEIVA_ADMIN_TOKEN`: bearer secreto das rotas administrativas.
- `TRELLO_API_KEY` e `TRELLO_API_SECRET`: credenciais OAuth 1.0 do Power-Up.
- `PUBLIC_API_URL`: base pública do callback Trello; padrão `https://neiva-ai-api.onrender.com`.
- `ASAAS_API_KEY`, `ASAAS_BASE_URL` e `ASAAS_WEBHOOK_TOKEN`: checkout e autenticação de webhooks.
- `CHECKOUT_CLAIM_SECRET`: segredo recomendado para claims do checkout; se ausente, o serviço usa o token do webhook ou a chave Asaas.
- `SITE_URL`: URL HTTPS do site para retornos do checkout. Ausente ou local usa a página de retorno da API.
- `CORS_ORIGIN_REGEX`: libera origens adicionais controladas, quando necessário.

Não coloque esses segredos no Git, no site ou no executável. Em produção, use PostgreSQL; as alterações de esquema atuais são aditivas no startup e ainda não usam Alembic.

## Executar e testar

Na raiz do repositório:

```powershell
.\.venv\Scripts\python.exe -m uvicorn ai_service.app.main:app --reload
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Rotas principais

- `GET /health`
- `POST /v1/auth/register`, `/v1/auth/sign-in`, `/v1/auth/app-login` e `/v1/auth/logout`
- `GET /v1/auth/session`
- `GET /v1/billing/plans`
- `POST /v1/billing/checkout` — requer bearer de sessão web e `Idempotency-Key`
- `GET /v1/billing/orders/{public_id}`
- `POST /v1/webhooks/asaas`
- `POST /v1/cuts`
- `POST /v1/integrations/trello/start`
- `GET /v1/integrations/trello/callback`
- `GET /v1/integrations/trello/status/{connection_id}`
- `POST /v1/admin/clients` — retorna um `activation_code` de uso único, não um token permanente
- `POST /v1/admin/billing/subscriptions`

O webhook, e não o retorno do navegador, é a fonte de ativação do pagamento. Antes de liberar produção, valide o ciclo completo em Asaas sandbox e a concorrência em PostgreSQL.
