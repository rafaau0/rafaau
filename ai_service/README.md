# API da IA Neiva

Esta pasta é implantada como um serviço separado no Render. A chave `OPENAI_API_KEY`
fica somente nas variáveis secretas do Render — nunca no aplicativo de quem usa.

## Variáveis exigidas no Render

- `OPENAI_API_KEY`: chave da conta que oferece a IA.
- `NEIVA_ADMIN_TOKEN`: senha longa e aleatória para criar chaves de clientes.
- `DATABASE_URL`: URL interna do PostgreSQL criado no Render.
- `OPENAI_MODEL`: opcional; padrão `gpt-5-mini`.
- `TRELLO_API_KEY`: chave pública do Power-Up Neiva Planner.
- `TRELLO_API_SECRET`: OAuth Secret do Power-Up; nunca deve ir para o desktop ou Git.
- `PUBLIC_API_URL`: opcional; padrão `https://neiva-ai-api.onrender.com` e usado no callback OAuth.

## Criar uma chave de cliente

Após o deploy, faça um `POST` em `/v1/admin/clients` usando `Authorization: Bearer <NEIVA_ADMIN_TOKEN>` e JSON como `{"name":"Nome do cliente","monthly_limit":30}`. A resposta contém `access_token` apenas uma vez. Entregue-o ao cliente, que o cola em Configurações > IA NEIVA.

## Rotas

- `GET /health`: verifica se a API está no ar.
- `POST /v1/cuts`: análise de cortes; exige a chave de acesso do cliente.
- `POST /v1/admin/clients`: cria a chave de um cliente; exige a senha de administrador.
- `POST /v1/integrations/trello/start`: inicia OAuth 1.0 para um aplicativo autenticado.
- `GET /v1/integrations/trello/callback`: callback HTTPS chamado pelo Trello.
- `GET /v1/integrations/trello/status/{connection_id}`: entrega o resultado somente à licença que iniciou o fluxo.
