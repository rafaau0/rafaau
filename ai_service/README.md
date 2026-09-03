# API da IA Neiva

Esta pasta é implantada como um serviço separado no Render. A chave `OPENAI_API_KEY`
fica somente nas variáveis secretas do Render — nunca no aplicativo de quem usa.

## Variáveis exigidas no Render

- `OPENAI_API_KEY`: chave da conta que oferece a IA.
- `NEIVA_ADMIN_TOKEN`: senha longa e aleatória para criar chaves de clientes.
- `DATABASE_URL`: URL interna do PostgreSQL criado no Render.
- `OPENAI_MODEL`: opcional; padrão `gpt-5-mini`.

## Criar uma chave de cliente

Após o deploy, faça um `POST` em `/v1/admin/clients` usando `Authorization: Bearer <NEIVA_ADMIN_TOKEN>` e JSON como `{"name":"Nome do cliente","monthly_limit":30}`. A resposta contém `access_token` apenas uma vez. Entregue-o ao cliente, que o cola em Configurações > IA NEIVA.

## Rotas

- `GET /health`: verifica se a API está no ar.
- `POST /v1/cuts`: análise de cortes; exige a chave de acesso do cliente.
- `POST /v1/admin/clients`: cria a chave de um cliente; exige a senha de administrador.
