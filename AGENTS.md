# AGENTS.md

## 1. Objetivo do projeto

Este repositório contém o produto **Neiva Planner / rafaau**, voltado a criadores, freelancers e pequenas agências que organizam conteúdo para clientes.

Há três aplicações no mesmo repositório:

1. **Aplicativo desktop Windows** (`content_planner/`): mantém clientes e calendários editoriais localmente, exporta PDFs, envia planejamentos ao Trello e abre o DaVinci Resolve instalado para edição externa de vídeo.
2. **API remota** (`ai_service/`): mantém contas, licenças, planos, dispositivos, cotas de IA e cobrança; intermedeia chamadas à OpenAI; e protege o segredo OAuth do Trello.
3. **Site público e administração** (`neiva-site/`): landing page, cadastro/login para checkout, redirecionamento ao Asaas, consulta do status de ativação, download do aplicativo e painel privado `/admin` para administrar assinantes.

O código usa os nomes “Neiva Planner”, “Neiva” e “rafaau” para o mesmo produto. A marca pública mais recente no site/login é “rafaau”, mas nomes internos, executável, caminhos locais e API ainda usam “Neiva”. Não uniformizar isso sem levantar impactos de compatibilidade.

## 2. Stack utilizada

### Desktop

- Python 3.10+; CI usa Python 3.12.
- CustomTkinter + Tkinter/ttk para interface.
- SQLite via `sqlite3` para dados editoriais locais.
- `keyring` para tokens e metadados sensíveis no cofre do Windows.
- ReportLab para PDFs.
- Pillow para os assets da interface.
- Faster-Whisper para transcrição local em CPU/int8.
- FFmpeg/FFprobe para leitura, edição e renderização de vídeo.
- yt-dlp para download autorizado de vídeos do YouTube.
- Requests para API Neiva, Trello e demais HTTP.
- PyInstaller para gerar o executável Windows.
- DaVinci Resolve como editor externo inicialmente suportado; o caminho de `Resolve.exe` é detectado ou salvo no SQLite local.

Faster-Whisper e FFmpeg são usados pelo painel do DaVinci para transcrição local e detecção de silêncios. FFprobe, yt-dlp e outros módulos do antigo editor permanecem no código/build durante a validação, mas não são alcançáveis pela navegação atual. Não remover esse motor legado sem validar primeiro a integração externa e revisar as dependências compartilhadas.

### API

- FastAPI + Uvicorn.
- SQLAlchemy 2.
- PostgreSQL em produção quando `DATABASE_URL` é configurada; SQLite local (`neiva_ai.db`) como fallback.
- Pydantic.
- psycopg 3.
- requests-oauthlib para OAuth 1.0 do Trello.
- cryptography/AES-GCM para credenciais OAuth temporárias.
- OpenAI Responses API acessada diretamente com Requests.
- Asaas para checkout recorrente e webhooks de cobrança.

### Site

- React 19, TypeScript e Tailwind CSS 4.
- Vinext/Vite, compatível com APIs de Next (`app/`, `next/font`, metadata).
- OpenAI Sites + Cloudflare Workers/Wrangler para build/hosting.
- O projeto contém uma coleção grande de componentes shadcn/Base UI, mas a página real importa somente `ActivationStatus` e `CheckoutButton`; o restante de `components/ui/`, `hooks/use-mobile.ts` e `lib/utils.ts` é atualmente scaffold não alcançado pela aplicação.
- `.openai/hosting.json` não configura D1 nem R2; o site não possui banco próprio.

## 3. Estrutura de pastas

```text
/
├── content_planner/       Aplicativo desktop e serviços locais
├── ai_service/            API FastAPI implantada separadamente
├── neiva-site/            Landing page e checkout web
├── tests/                 Testes unittest do desktop e de partes da API
├── assets/                Logos, tema e metadados/licença do FFmpeg
├── scripts/               Preparação verificável do FFmpeg para o build
├── hooks/                 Hook do PyInstaller para Tkinter
├── .github/workflows/     CI Windows, auditoria, testes e empacotamento
├── NeivaPlanner.spec      Configuração do executável PyInstaller
├── requirements.txt       Dependências do desktop e build
├── README.md              Instruções gerais do desktop/API/Trello
└── INSTRUCOES_CLIENTE.txt Instruções curtas para distribuição
```

`database/`, `exports/`, `build/`, `dist/`, `.venv/` e caches existem localmente, mas são ignorados pelo Git. Não tratar conteúdo dessas pastas como fonte versionada. Em desenvolvimento, logs e exportações ficam em `exports/`; no executável, bancos, logs e exportações ficam sob `%LOCALAPPDATA%\NeivaPlanner`.

## 4. Arquitetura

### Visão geral

```text
Site React ── cadastro/login + checkout ──> API FastAPI ──> Asaas
                                                  │          │
                                                  │<── webhook
                                                  ├──> PostgreSQL/SQLite da API
                                                  ├──> OpenAI Responses API
                                                  └──> OAuth 1.0 do Trello

Desktop ── login/licença/cortes IA/OAuth Trello ─> API FastAPI
   ├── CRUD editorial ──> SQLite local por conta
   ├── credenciais ─────> cofre do Windows
   ├── cards ───────────> API REST do Trello (direto após OAuth)
   └── vídeo ───────────> DaVinci Resolve instalado no Windows
```

O desktop possui separação parcial entre interface, persistência e serviços, mas não segue MVC estrito. `content_planner/ui.py` é um controlador/view monolítico: cria telas, mantém estado, aplica limites de plano, dispara threads e coordena serviços. Banco, Trello, vídeo e PDF ficam em módulos separados.

A API também é monolítica: modelos SQLAlchemy, esquemas Pydantic, autenticação, cobrança, integrações e rotas estão todos em `ai_service/app/main.py`. Não há camada de repositório, Alembic ou módulos por domínio.

O site é uma landing page única. `app/page.tsx` é majoritariamente apresentação estática; os únicos fluxos com estado ficam nos dois componentes client-side.

Chamadas demoradas do desktop rodam em `threading.Thread(daemon=True)` e retornam à thread do Tk por `self.after(...)`. Manter operações de rede, Whisper e FFmpeg fora da thread da UI.

## 5. Banco de dados

### SQLite local do desktop

Implementado em `content_planner/database.py` com SQL manual e dataclasses `Client` e `Post`.

Tabelas:

- `clientes`: nome, nicho, Instagram, frequência, objetivo, observações, `operation_id` idempotente e timestamps.
- `posts`: cliente, data ISO `YYYY-MM-DD`, tipo, plataforma, título, descrição, legenda, CTA, status, `trello_card_id` e `operation_id`; FK para `clientes` com `ON DELETE CASCADE`.
- `configuracoes`: chave/valor para configurações não secretas e compatibilidade legada.

Há índice `idx_posts_client_date` e índices únicos parciais para `operation_id`. Cada conexão ativa `PRAGMA foreign_keys = ON` e faz commit ao sair do context manager.

O banco padrão é isolado por conta em `database/accounts/<account_id>/content_planner.db`. Sem conta atual (licença legada), usa `database/content_planner.db`. Em build instalado, a raiz equivalente é `%LOCALAPPDATA%\NeivaPlanner\database`. Uma conta moderna não recebe automaticamente o banco legado; associação/migração de titularidade ainda precisa de um fluxo explícito.

Não há versionamento formal do esquema do desktop. `CREATE TABLE IF NOT EXISTS` não adiciona colunas novas a bancos antigos; qualquer evolução de esquema precisa de migração explícita e teste com banco existente.

### Banco remoto da API

Modelos definidos em `ai_service/app/main.py`:

- `accounts`: identidade, e-mail único, hash de senha, estado ativo.
- `clients`: licença técnica vinculada opcionalmente a uma conta, hash de token, plano, cota mensal, limite de dispositivos e estado ativo.
- `monthly_usage`: consumo mensal de análises por cliente, reservado por atualização atômica e devolvido quando a chamada de IA falha.
- `activation_codes`: código legado de uso único por cliente.
- `device_tokens`: sessão do aplicativo por dispositivo.
- `subscriptions`: assinatura Asaas e estado da cobrança.
- `processed_webhooks`: idempotência de eventos.
- `account_sessions`: bearer token de duas horas usado pelo site para iniciar checkout.
- `login_throttles`: limite persistente de tentativas por hash de conta/origem; nunca armazena e-mail/IP em claro.
- `checkout_orders`: pedido, claim token, chave de idempotência, checkout Asaas e vínculo posterior à licença.
- `trello_oauth_requests`: estado efêmero do OAuth, vinculado à licença e criptografado.
- `admin_users`: operadores administrativos separados das contas de clientes; o primeiro é criado somente pelas variáveis de ambiente de bootstrap.
- `admin_sessions`: sessões administrativas opacas, armazenadas somente por hash e com expiração absoluta de duas horas.
- `admin_audit_logs`: trilha das alterações de acesso, plano, limites e revogação de dispositivos, sempre com justificativa.

As tabelas são criadas no evento de startup. Três tabelas recebem migrações aditivas manuais por `ALTER TABLE`. Não há Alembic, rollback ou controle de versão de migrations; alterações destrutivas ou restrições novas são especialmente sensíveis.

## 6. Principais módulos e responsabilidades

### Desktop

- `content_planner/main.py`: configura logs, exige login e reinicia a UI ao adicionar/trocar/remover conta.
- `content_planner/account_login.py`: cadastro, login do app, validação da sessão salva, ID estável do dispositivo e ativação legada. A URL da API está fixa no código.
- `content_planner/account_sessions.py`: índice de contas locais, conta ativa e tokens por conta no keyring.
- `content_planner/account_manager.py`: modal de troca/remoção; revoga o token remoto antes de remover a sessão local.
- `content_planner/plan_rules.py`: limites dos planos `free`, `essencial` e `pro`; plano pago de conta moderna exige confirmação online da API, enquanto ausência de conta continua sendo licença legada Pro.
- `content_planner/ui.py`: dashboard, clientes, planejamento/calendário, lançador do DaVinci, configurações, modais e orquestração geral. Métodos da edição interna permanecem temporariamente sem entrada de navegação.
- `content_planner/database.py`: CRUD local e configurações.
- `content_planner/pdf_generator.py`: PDF mensal com capa, calendário e tabela de conteúdos.
- `content_planner/trello_auth.py`: inicia OAuth pela API, abre navegador, consulta status e lista identidade/quadros.
- `content_planner/trello_api.py`: cria/reutiliza listas e cards diretamente no Trello; usa marcador HTML estável para idempotência.
- `content_planner/video_subtitles.py`: probe, transcrição, SRT/VTT, ASS e renderização FFmpeg.
- `content_planner/effects.py`: geração de ASS com animações e destaque por palavra.
- `content_planner/silence_editor.py`: detecção, planejamento e aplicação de cortes de silêncio, incluindo remapeamento de timestamps.
- `content_planner/youtube_downloader.py`: metadados e download autorizado com yt-dlp.
- `content_planner/clip_finder.py`: heurística local de cortes.
- `content_planner/clip_ai.py`: cliente da rota remota `/v1/cuts` e validação defensiva do resultado.
- `content_planner/video_editor.py`: valida, detecta e inicia `Resolve.exe` sem usar shell.
- `content_planner/secrets.py`: keyring, com variáveis de ambiente tendo precedência.
- `content_planner/ffmpeg_tools.py`: resolve binários empacotados antes do PATH.
- `content_planner/logging_setup.py`: log rotativo.
- `content_planner/design_system.py`: tokens visuais.
- `content_planner/rth_tk.py`, `hooks/...`, `NeivaPlanner.spec`: suporte ao empacotamento Windows.

### API e site

- `ai_service/app/main.py`: toda a API e modelos remotos.
- `neiva-site/app/page.tsx`: conteúdo, preços e landing page.
- `neiva-site/components/checkout-button.tsx`: cadastro/login, checkout e armazenamento local do claim token.
- `neiva-site/components/activation-status.tsx`: polling curto do status da licença após retorno do Asaas.
- `neiva-site/app/admin/page.tsx` e `components/admin-panel.tsx`: login e superfície administrativa de assinantes, assinaturas, consumo e dispositivos.
- `neiva-site/app/admin-api/route.ts`: proxy estritamente limitado a `/v1/admin/*`; mantém o cookie administrativo no mesmo domínio do site e evita dependência de cookies de terceiros.
- `neiva-site/vite.config.ts`: integração Vinext/OpenAI Sites/Cloudflare.

## 7. Fluxos importantes

### Login, conta e plano

1. O desktop obtém/cria `NEIVA_DEVICE_ID` no keyring.
2. `/v1/auth/app-login` valida PBKDF2, cria/renova um `DeviceToken` e devolve token bearer + dados da conta/plano.
3. O token e o índice de contas ficam no keyring; o desktop seleciona o SQLite específico da conta.
4. Em inicializações seguintes, `/v1/auth/session` revalida licença e atualiza os metadados locais.
5. Limites de clientes/posts/PDF e bloqueios de Trello/vídeo são aplicados pela UI com `PlanRules`.

### Planejamento

Clientes e posts são CRUD local. O calendário consulta por cliente/mês. A exportação busca os posts daquele mês e gera PDF. O plano grátis conta PDFs numa chave local `PLAN_PDF_EXPORTS_YYYY-MM`.

### Trello

1. Desktop usa sua licença bearer para pedir `/v1/integrations/trello/start`.
2. API guarda secret temporário criptografado com chave derivada de `TRELLO_API_SECRET` e devolve URL de autorização.
3. Usuário autoriza no navegador; callback da API troca o request token pelo access token.
4. Desktop consulta o status e recebe API key pública + token uma única vez.
5. Desktop lista quadros e depois fala diretamente com `api.trello.com`.
6. Para cada cliente/mês, cria/reutiliza uma lista. Cada card leva `<!-- neiva-planner-post:<id> -->`; uma repetição busca esse marcador antes de criar, e `trello_card_id` evita reenvio normal.

### Vídeo e cortes

O Estúdio de Vídeo lê `DAVINCI_RESOLVE_PATH` do SQLite local, tenta detectar `Resolve.exe` em `Program Files` e inicia o processo diretamente, sem shell. Ele também instala `assets/davinci/rafaau_timeline.py` em `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Edit`; o FFmpeg é copiado para `%LOCALAPPDATA%\NeivaPlanner\davinci_integration` e referenciado por um `config.json` sem segredos. Não usar `fusion.UIManager` nesse script: ele retorna `None` no Resolve gratuito e dispara a oferta do Studio. O comando chama o próprio aplicativo com `--davinci-dialog` para abrir confirmações externas no tema do rafaau; `ctypes.windll.user32.MessageBoxW` permanece apenas como fallback compatível com a edição gratuita.

Dentro do Resolve, o comando usa a API oficial de scripting. Ele só aceita uma timeline simples com um vídeo, um áudio vinculado do mesmo arquivo, fonte acessível, recortes A/V alinhados e sem retiming. O FFmpeg executa `silencedetect` somente no intervalo usado pelo clipe. Após duas confirmações nativas, a aplicação cria uma timeline vazia e anexa todos os trechos não silenciosos sequencialmente por `MediaPool.AppendToTimeline`, sem `recordFrame`. Os frames de origem são calculados com `TimelineItem.GetLeftOffset(False)`: não reutilizar `GetSourceStartFrame`, pois o Resolve pode devolvê-lo em timecode absoluto e fazer a cópia apontar para um trecho errado. A original não é modificada. Timelines complexas são deliberadamente bloqueadas até existir uma estratégia validada para preservar composição, efeitos, transições e múltiplas faixas.

As legendas não usam `Timeline.CreateSubtitlesFromAudio`, pois a matriz oficial limita transcrição automática ao Resolve Studio. O painel chama o próprio executável com `--davinci-transcribe <request.json>`; `content_planner/davinci_caption_worker.py` usa Faster-Whisper local, remapeia palavras de acordo com os trechos mantidos e grava SRT sob `%LOCALAPPDATA%\NeivaPlanner\davinci_integration\captions`. O painel tenta `MediaPool.ImportMedia`; a API oficial não oferece inserção direta de SRT em faixa de subtitle, portanto o usuário precisa arrastar o item/arquivo para a nova timeline. Na primeira execução, o modelo `small` pode ser baixado para o cache do usuário.

Arquivos principais desse fluxo: `content_planner/davinci_integration.py` (instalação), `content_planner/davinci_caption_worker.py` (transcrição/remapeamento), `content_planner/davinci_dialog.py` (janelas externas temáticas), `content_planner/video_editor.py` (detecção/abertura), `assets/davinci/rafaau_timeline.py` (painel e processamento no Resolve) e `NeivaPlanner.spec` (empacotamento). O restante do motor anterior baseado em `VideoProject`, FFmpeg e yt-dlp permanece temporariamente no código, sem acesso pela navegação.

### Site, checkout e ativação

O site cadastra ou autentica a conta na API. Plano grátis termina após criar a conta. Planos pagos criam `CheckoutOrder`, abrem checkout recorrente mensal por cartão no Asaas e guardam um claim token no `localStorage`. Webhooks idempotentes ativam/atualizam `Client` e `Subscription`. O retorno do site consulta o pedido usando public ID + claim token. O desktop obtém o plano atualizado no login/sessão.

### Administração

O primeiro operador é criado no startup da API somente quando `NEIVA_ADMIN_EMAIL` e `NEIVA_ADMIN_PASSWORD` estão configurados e ainda não existe esse e-mail. O login em `/admin` cria um token opaco cujo hash fica em `admin_sessions`; o navegador recebe cookie `HttpOnly`, `Secure` em produção e `SameSite=None`. O site acessa a API pelo proxy same-origin `/admin-api`, restrito por validação de URL às rotas administrativas. Leituras exigem sessão válida; escritas exigem também `X-Admin-CSRF`, derivado no servidor com `ADMIN_SESSION_SECRET`, e justificativa. Suspensão/reativação altera conta e licença em conjunto; mudança manual de plano/limites não altera o registro do provedor e pode ser substituída pelo próximo webhook Asaas. Nunca retornar senha, hashes ou tokens de dispositivo. O painel administra assinantes remotos, não os clientes/posts do SQLite local.

## 8. APIs e integrações

Rotas reais da API:

- `GET /health`
- `POST /v1/auth/register`
- `POST /v1/auth/sign-in` (sessão curta do site)
- `POST /v1/auth/app-login` (sessão por dispositivo do desktop)
- `GET /v1/auth/session`
- `POST /v1/cuts`
- `POST /v1/activate` (legado)
- `POST /v1/integrations/trello/start`
- `GET /v1/integrations/trello/callback`
- `GET /v1/integrations/trello/status/{connection_id}`
- `GET /v1/billing/plans`
- `POST /v1/billing/checkout`
- `GET /v1/billing/orders/{public_id}`
- `GET /v1/billing/return` (fallback temporário)
- `POST /v1/webhooks/asaas`
- `POST /v1/admin/clients`
- `POST /v1/admin/billing/subscriptions`
- `POST /v1/admin/auth/sign-in`, `POST /v1/admin/auth/sign-out`, `GET /v1/admin/auth/session`
- `GET /v1/admin/dashboard`, `GET /v1/admin/customers`, `GET/PATCH /v1/admin/customers/{client_id}`
- `DELETE /v1/admin/customers/{client_id}/devices/{device_id}`, `POST /v1/admin/customers/{client_id}/revoke-devices`
- `GET /v1/admin/audit`

Integrações externas: OpenAI Responses API, Asaas, Trello REST/OAuth 1.0, YouTube via yt-dlp, GitHub Releases para download e Cloudflare/OpenAI Sites para hospedagem web.

## 9. Autenticação, autorização e segurança

- Senhas remotas usam PBKDF2-HMAC-SHA256 com sal individual e 600.000 iterações.
- Tokens brutos de conta/licença/dispositivo, códigos e claims são armazenados na API somente como SHA-256; exceção temporária: `CheckoutOrder.activation_code` legado fica reversível até a ativação.
- Sessões web expiram em duas horas. Tokens de dispositivo não possuem expiração no código atual.
- As duas rotas administrativas técnicas legadas usam bearer comparado com `NEIVA_ADMIN_TOKEN` via `hmac.compare_digest`. O painel web usa operador/senha, cookie `HttpOnly`, sessão de duas horas, CSRF e auditoria.
- Webhook Asaas exige `asaas-access-token` igual a `ASAAS_WEBHOOK_TOKEN` e registra event ID.
- Segredo OAuth Trello e chave OpenAI permanecem no servidor. Credenciais OAuth temporárias usam AES-GCM; o access token final é entregue uma vez ao cliente.
- Desktop armazena tokens no keyring e nunca deve voltar a gravá-los em SQLite, arquivos, logs ou Git.
- O CORS da API aceita localhost, o domínio público, `www` e um hostname específico de preview; regex adicional é configurável.

## 10. Variáveis de ambiente e configurações

### API

- `DATABASE_URL`: PostgreSQL de produção; sem ela usa SQLite local.
- `OPENAI_API_KEY`: obrigatória para cortes por IA.
- `OPENAI_MODEL`: opcional, padrão `gpt-5-mini`.
- `NEIVA_ADMIN_TOKEN`: obrigatória para rotas administrativas.
- `NEIVA_ADMIN_EMAIL`, `NEIVA_ADMIN_PASSWORD`: bootstrap do primeiro operador do painel; a senha exige no mínimo 12 caracteres e não é atualizada automaticamente em startups posteriores.
- `NEIVA_ADMIN_RESET_PASSWORD`: recuperação excepcional. Somente `true` redefine o hash do operador indicado por `NEIVA_ADMIN_EMAIL`, revoga suas sessões e registra auditoria; retornar para `false` logo após o deploy.
- `ADMIN_SESSION_SECRET`: chave para CSRF das sessões administrativas; se ausente usa `NEIVA_ADMIN_TOKEN` por compatibilidade.
- `ADMIN_COOKIE_SECURE`: padrão seguro; definir `false` somente no HTTP local.
- `TRELLO_API_KEY`, `TRELLO_API_SECRET`: credenciais do Power-Up; o secret também cifra estado OAuth.
- `PUBLIC_API_URL`: base do callback OAuth; padrão de produção hardcoded.
- `ASAAS_API_KEY`, `ASAAS_BASE_URL`, `ASAAS_WEBHOOK_TOKEN`: checkout e webhook.
- `SITE_URL`: retorno do checkout; se ausente/localhost, usa a página fallback da API.
- `CORS_ORIGIN_REGEX`: somente para liberar origens adicionais controladas, especialmente staging.

### Desktop

- `LOCALAPPDATA`: raiz do banco/log no executável.
- `TRELLO_APP_KEY`: override da API key pública local.
- `TRELLO_API_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_ID`: overrides com precedência sobre valores salvos.
- `TCL_LIBRARY`, `TK_LIBRARY`: definidos pelo runtime hook no executável.
- A base da API (`https://neiva-ai-api.onrender.com`) e o site (`https://rafaau.site`) são constantes, não variáveis.

### Site/build

- A API de produção/staging é escolhida por hostname e está hardcoded nos componentes.
- `CODEX_SANDBOX`, `WRANGLER_WRITE_LOGS`, `WRANGLER_LOG_PATH` e `MINIFLARE_REGISTRY_PATH` são configurações de tooling local, não regras de produto.
- `ai_service/.env.example` documenta as chaves sem conter valores secretos. Não existe configuração versionada de deploy da API (por exemplo `render.yaml`, Dockerfile ou Procfile); o comando/configuração exata de produção é desconhecido pelo repositório.

## 11. Convenções utilizadas

- Python usa type hints, dataclasses e funções pequenas nos serviços, mas `ui.py`, `effects.py` e `silence_editor.py` também contêm várias instruções compactadas em uma linha. Preserve o estilo local no trecho tocado, mas prefira legibilidade em código novo.
- Mensagens ao usuário são majoritariamente em português do Brasil.
- Datas de posts são strings ISO; não mudar o formato sem migrar consultas, PDF e Trello.
- Status reconhecidos: `Pendente`, `Em andamento`, `Concluído`.
- Tipos/plataformas são listas fixas em `ui.py`.
- Operações externas devem ter timeout e exceções convertidas em mensagens compreensíveis.
- Atualizações de Tk devem ocorrer na thread principal via `after`.
- Segredos devem passar por `content_planner/secrets.py` ou variáveis secretas do servidor.
- Integração Trello depende do marcador de card e das chaves `TRELLO_LIST_<client>_<year>_<month>`; preservar ambos para idempotência.
- Compatibilidade com execução normal e PyInstaller (`sys.frozen`, `sys._MEIPASS`) é uma regra transversal.

## 12. Comandos importantes

Na raiz, PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r ai_service\requirements.txt
python -m content_planner
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
powershell -ExecutionPolicy Bypass -File scripts\prepare_ffmpeg.ps1
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean NeivaPlanner.spec
```

API local:

```powershell
cd ai_service
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Site:

```powershell
cd neiva-site
npm install
npm run dev
npm run lint
npm run format
npm run build
npm run start
```

O workflow `.github/workflows/quality.yml` instala dependências, executa `pip check`, `pip-audit`, testes Python, lint/build do site, baixa/verifica FFmpeg e gera o EXE. Tags estáveis exatas (`vX.Y.Z`) exigem certificado configurado, assinam e validam o executável antes da release oficial. Tags SemVer com sufixo (`vX.Y.Z-sufixo`, como `-test.1`, `-beta.1` ou `-rc.1`) podem publicar uma prerelease não assinada. Tags `v*` fora desses formatos falham. Atualmente, o botão de download do site está temporariamente fixado na prerelease não assinada `v1.1.1-test.1` para testes do pipeline; antes de distribuir uma versão oficial, restaurar `neiva-site/app/page.tsx` para `releases/latest/download/rafaau_v1.exe`. O desktop não possui atualizador automático.

Estado verificado diretamente em 2026-09-05: 41 testes Python passam; `npm run lint` e `npm run build` passam para o código publicado do site. Os componentes UI de scaffold não utilizados ficam fora do escopo do lint da aplicação. O build PyInstaller anterior incluiu FFmpeg, FFprobe e `content_planner.paths`; o artefato local permanece sem assinatura por não haver certificado no workspace.

## 13. Regras para modificações futuras

1. Ler este arquivo e os módulos diretamente envolvidos antes de editar; o código é a fonte principal da verdade.
2. Não versionar bancos, exportações, vídeos, executáveis, caches, `.env` ou segredos.
3. Não colocar `OPENAI_API_KEY`, `TRELLO_API_SECRET`, `NEIVA_ADMIN_TOKEN`, credenciais administrativas ou chaves Asaas no desktop/site.
4. Ao alterar login, plano ou cobrança, analisar em conjunto API, `account_sessions.py`, `account_login.py`, `plan_rules.py` e checkout do site.
   Para administração, revisar também `AdminSession`, CSRF, `/admin-api`, auditoria e os efeitos do próximo webhook Asaas.
5. Ao alterar persistência, preservar isolamento por conta, migração de instalações legadas e bancos já existentes.
6. Ao alterar Trello, preservar entrega única do token, vínculo da requisição ao cliente e idempotência de listas/cards.
7. Ao alterar vídeo, validar arquivo local e build PyInstaller, disponibilidade de FFmpeg/FFprobe, vídeo sem áudio, caminhos Windows e custo de CPU/RAM.
   Durante a migração para editor externo, validar também detecção manual/automática e abertura do DaVinci Resolve real.
8. Executar testes Python após mudanças. Se tocar o site, executar lint e build, distinguindo erros preexistentes do scaffold.
9. Não assumir que texto do site corresponde ao produto: comparar qualquer promessa comercial com desktop/API.
10. Não atualizar FFmpeg sem atualizar URL, versão, SHA-256, licença e `BUILD_INFO.txt` de forma coerente.
11. Não enfraquecer a separação de releases: stable `vX.Y.Z` deve continuar exigindo assinatura válida; somente tags com sufixo podem ser publicadas como prerelease sem assinatura.
12. O link direto para `v1.1.1-test.1` no site é temporário. Não manter uma prerelease não assinada como download público ao encerrar os testes; restaurar o canal `releases/latest` junto da publicação stable assinada.

## 14. Partes sensíveis

- `ai_service/app/main.py`: autenticação, hashes, cobrança, webhook, quotas e OAuth no mesmo arquivo; regressões têm impacto remoto.
- `content_planner/database.py`: caminhos por conta e migração legada podem causar perda ou mistura de dados.
- `content_planner/account_sessions.py` e `secrets.py`: identidade ativa e todos os tokens locais.
- `content_planner/ui.py`: estado em memória e callbacks assíncronos; uma mudança visual pode alterar regra de produto.
- `content_planner/video_subtitles.py` e `silence_editor.py`: filtros FFmpeg complexos, sincronização A/V e alto custo computacional.
- `NeivaPlanner.spec`, runtime hook Tk e assets FFmpeg: qualquer omissão pode funcionar em desenvolvimento e falhar somente no EXE.
- Webhook e `activate_paid_order`: devem continuar idempotentes; nunca ativar licença apenas pelo retorno do navegador.

## 15. Registro histórico da análise inicial

Esta seção descreve o estado anterior às correções iniciadas após o relatório de QA. Não a use como status atual; consulte a seção 18. Ela foi preservada para explicar a origem das regressões e decisões.

### Alta prioridade

- **Dispositivos não podem ser liberados no servidor.** Remover/sair de uma conta no desktop apaga apenas o keyring local. Não há rota de logout/revogação de `DeviceToken`; tokens antigos continuam contando para `device_limit`, embora a mensagem da API diga para “sair de um deles”.
- **Trello não está isolado por conta local.** `TRELLO_API_KEY`, `TRELLO_TOKEN` e `TRELLO_BOARD_ID` usam chaves globais do serviço keyring e também variáveis de processo. Ao trocar de conta, outra conta pode herdar o mesmo Trello/quadro. O SQLite é isolado, mas essas credenciais não.
- **Fotos de encarte não são inseridas pelo gerador atual.** `encarte_service` encontra e inclui o caminho das imagens no dicionário de produtos, porém `encarte_legacy.build_jsx` só usa descrição e preço. A promessa de preencher fotos está incompleta.
- **“Ativar edição dinâmica” não controla a renderização.** `dynamic_edit_enabled` é salvo, mas não é consultado por `render`; zoom/movimento são aplicados conforme seus próprios flags, que começam ativos. A opção principal pode não ter efeito.

### Segurança e robustez

- Não há rate limiting, lockout ou proteção equivalente nas rotas de login, cadastro, ativação e admin além do segredo bearer.
- Tokens de dispositivo não expiram e não há limpeza de tokens/sessões expiradas. `last_seen_at` só muda no login.
- A cota de IA é incrementada e commitada antes da chamada OpenAI; falhas do provedor consomem crédito.
- Limites de clientes/posts/PDF e bloqueios de vídeo/encarte são locais na UI. Eles são adequados como UX, não como barreira de segurança contra cliente modificado.
- `get_secret` silencia falhas do keyring durante leitura e retorna fallback, o que pode parecer “sessão ausente” sem diagnóstico.
- Threads de fundo podem concluir depois que a tela foi recriada; vários callbacks acessam widgets sem tratar `TclError`.
- Ferramentas FFmpeg de silêncio não têm timeout e `apply_cuts` presume que existe uma faixa de áudio.

### Produto, arquitetura e manutenção

- `ui.py` e `ai_service/app/main.py` concentram responsabilidades demais e aumentam o risco de mudanças cruzadas.
- Não há migrations versionadas nem testes de upgrade de esquema da API/desktop.
- Cobertura de testes é focada em helpers, banco básico, planos e Trello. Não cobre cobrança/webhooks completos, login real da API, expiração/limite de dispositivos, PDFs, transcrição/renderização, YouTube, Photoshop nem site.
- O site anuncia “7 dias de teste grátis” e preços anuais, mas o checkout implementado cria cobrança mensal imediata por cartão e não possui ciclo anual/trial no payload.
- O site sugere operação compartilhada/equipe e “responsável”, mas o desktop usa SQLite local por conta, sem sincronização, colaboração remota ou campo de responsável.
- Há inconsistência de marca e nomenclatura entre Neiva Planner e rafaau.
- `ai_service/README.md` está desatualizado: omite rotas de conta/cobrança e variáveis Asaas/site/CORS; diz que `/v1/admin/clients` retorna `access_token`, mas o código retorna `activation_code`.
- `README.md` diz que se configura URL/chave da IA em Configurações, mas a URL é fixa e a tela trabalha com conta/código de ativação.
- `INSTRUCOES_CLIENTE.txt` aponta o backup do banco legado único; contas modernas ficam em subpastas `accounts/<id>`.
- O fallback `/v1/billing/return` é explicitamente temporário e contém textos com mojibake (`LicenÃ§a`, etc.) no código.
- Cadastro social, recuperação de senha e vídeo demonstrativo do site são placeholders explícitos.
- Componentes UI do site estão quase todos sem uso e causam todos os erros atuais de lint. Dependências associadas a eles (`@base-ui/react`, shadcn, cmdk, date-fns, embla, input-otp, lucide, react-day-picker, panels, recharts etc.) não participam da página atual; confirmar intenção antes de remover, pois parecem scaffold gerado.
- Funções/valores aparentemente sem uso: `youtube_downloader.download_audio`, `TrelloAPI.create_cards_for_posts`, `design_system.secondary_button` (apenas importado), `video_subtitles.force_style`, parâmetro `effects.write_ass(..., highlight=...)` e variável intermediária `subtitles_words`.
- `encarte_legacy.py` também possui um fluxo CLI antigo (`main`) não chamado pelo aplicativo, mas suas funções de Photoshop continuam ativas no fluxo novo.
- O site não entra no workflow de CI.

## 16. O que um novo agente deve saber

- Não existe um backend para sincronizar clientes/posts: o backend remoto cuida de identidade/licença/integrações, enquanto o conteúdo editorial é local.
- Trocar conta troca o arquivo SQLite, mas hoje não troca corretamente as credenciais globais do Trello.
- Licenças legadas sem `SavedAccount` recebem regras Pro por compatibilidade.
- A API cria automaticamente uma licença `free` para cada conta; uma licença paga reutiliza esse mesmo `Client` quando o webhook confirma o pedido.
- O fluxo confiável de pagamento é o webhook, não o redirect do browser.
- O plano grátis possui cota de IA zero e não pode iniciar OAuth Trello na API; vídeo e Trello também são ocultados pela UI.
- A primeira transcrição pode baixar o modelo Whisper no cache do usuário e parecer lenta; isso não está empacotado como asset.
- O executável inclui FFmpeg somente se os binários existirem em `assets/ffmpeg` na hora do build. No Git ficam apenas licença e informações do build.
- A interface de vídeo suporta somente DaVinci Resolve. O painel atua sobre a timeline aberta, mas a primeira versão aceita apenas um vídeo com um áudio do mesmo arquivo, vinculado/alinhado e sem retiming; sempre cria nova timeline. As legendas locais funcionam sem Studio, mas o SRT precisa ser arrastado para a timeline porque a API não expõe inserção direta em faixa de subtitle.
- Informações não determinadas pelo repositório: infraestrutura exata/deploy da API, configuração real de produção no Render/Asaas/Trello/OpenAI, processo de assinatura do EXE, origem/validação dos depoimentos do site e existência de monitoramento/backups remotos.

## 17. Baseline histórico de QA fornecido para o commit original

Foi fornecido posteriormente um relatório de QA abrangente para o commit `1439918ab1e70e54067e4c3877f533fa7fc0fae9`, o mesmo HEAD analisado na criação deste arquivo. O relatório é evidência secundária importante, mas seus scripts e resultados brutos não estão versionados neste repositório. Antes de corrigir um caso, reproduzir o cenário em fixture isolada e convertê-lo em teste automatizado estável. Nunca executar os scripts diagnósticos descritos no relatório contra produção.

Resumo informado pelo QA:

- 216 cenários: 116 aprovados, 64 falhos, 24 não executados e 12 bloqueados.
- 51 bugs: 7 críticos, 27 altos, 16 médios e 1 baixo.
- Estimativa por `trace`: 1.269 de 3.981 linhas executáveis Python alcançadas (31,9%); não é cobertura de branches nem inclui frontend.
- Instalação Python limpa, `pip check`, 30 testes, TypeScript, build/runtime do site e build PyInstaller passaram.
- O EXE de QA incluiu FFmpeg, FFprobe, Tcl/Tk e assets, mas estava sem assinatura Authenticode.
- `pip-audit` e `npm audit` não reportaram vulnerabilidades conhecidas nas versões testadas; a varredura limitada de segredos não encontrou candidatos.
- SQLite respondeu bem nos probes de até 10.000 posts, mas isso não cobre widgets, contenção ou operação real prolongada.
- Asaas, Trello, OpenAI e Photoshop reais, PostgreSQL legado/concorrente, Windows limpo e mídia longa/4K permaneceram bloqueados ou não testados.
- Conclusão do relatório: produto não pronto para clientes reais; nota de prontidão para produção 2/10 e nota geral 4/10.

### Bugs críticos confirmados pelo QA

- `QA-001`: logout não revoga token nem libera dispositivo.
- `QA-002`: desativar `Account` não invalida token se o `Client` continuar ativo; `current_client` não verifica a conta vinculada.
- `QA-004`: entitlements pagos dependem de metadado local adulterável e plano desconhecido/ausente pode cair em Pro por compatibilidade legada.
- `QA-005`: acesso não é conciliado com vencimento, inadimplência, cancelamento e `current_period_end` da assinatura.
- `QA-006`: webhook antigo de confirmação pode reativar licença já estornada; ordenação temporal/precedência financeira não é modelada.
- `QA-015`: credenciais Trello vazam entre contas locais.
- `QA-022`: encarte pode salvar descrição nova com foto ou preço antigo e tratar ausência de camada apenas como log.

### Bugs altos por domínio

#### Conta, cobrança e IA

- `QA-003`: não há limitação de tentativas de login.
- `QA-007`: confirmação posterior não restaura plano/cota/dispositivos após o login ter convertido licença suspensa em Free.
- `QA-008`: checkout e submits repetidos não possuem idempotency key e podem criar vários pedidos/sessões.
- `QA-009`: falhas OpenAI, configuração ausente e payload grande debitam crédito.
- `QA-010`: read-modify-write da quota sofre corrida; duas requisições podem usar o último crédito e persistir contagem incorreta.
- `QA-011`: JSON externo inválido e webhook aninhado malformado podem gerar HTTP 500 em vez de erro controlado.
- `QA-013`: trocas `fetch_request_token`/`fetch_access_token` do OAuth Trello não têm timeout explícito.
- `QA-016`: o primeiro perfil moderno pode receber automaticamente o banco legado sem confirmação de titularidade.
- `QA-048`: oferta de sete dias/anual diverge do checkout mensal com primeiro vencimento em aproximadamente um dia.

#### Dados, PDF, encartes e Trello

- `QA-017`: seletores por nome escolhem o primeiro registro quando há clientes homônimos; identidade deve ser por ID.
- `QA-019`: PDF omite legenda, CTA e descrição completa sem indicar que é resumo.
- `QA-020`: tabela do PDF pode imprimir entidades HTML e deixar títulos longos ultrapassarem células.
- `QA-021`: slugs iguais de clientes distintos geram o mesmo nome de PDF e sobrescrevem o arquivo.
- `QA-023`: mais de 24 produtos são truncados sem aviso.
- `QA-024`: preço negativo, texto, fórmula sem cache e vazio podem prosseguir; não existe parser monetário de domínio.
- `QA-026`: trocar planilha depois da validação mantém `encarte_products` da origem anterior.
- `QA-027`: fuzzy match com limiar 70 pode aceitar foto de variante errada sem pedir confirmação.
- `QA-028`: marcador Trello usa somente o ID local do post e colide entre bancos/contas.
- `QA-029`: cache `TRELLO_LIST_<client>_<year>_<month>` não inclui board ID e pode reutilizar lista de outro quadro.
- `QA-030`: dois envios concorrentes podem ambos não encontrar o marcador e criar cards duplicados.

#### Vídeo e execução

- `QA-031`: editar `Subtitle.text` não invalida `Subtitle.words`; ASS/MP4 word-highlight pode reutilizar o texto antigo.
- `QA-032`: divisão da transcrição calcula intervalos proporcionalmente em vez de usar timestamps reais das palavras.
- `QA-033`: job iniciado para vídeo A pode aplicar o resultado ao `self.video_project` já trocado para B.
- `QA-034`: os mesmos cortes de silêncio podem ser aplicados novamente ao vídeo já recortado.
- `QA-035`: várias exportações simultâneas escrevem no mesmo `<stem>_legendado.mp4` com `-y`.
- `QA-038`: probe FPS, detecção e aplicação de silêncios não têm timeout; alguns `TimeoutExpired` escapam como erro técnico.
- `QA-042`: centenas de cortes constroem `filter_complex` maior que o limite de linha de comando do Windows.

### Bugs médios e baixo

- `QA-012`: saída semanticamente inválida da OpenAI passa pela API; o desktop filtra parte, mas a API não valida o contrato completo.
- `QA-014`: normalização permite nome vazio e validação de e-mail/senha é insuficiente na API direta.
- `QA-018`: repositório SQLite aceita invariantes inválidos e não distingue operação repetida de homônimo legítimo.
- `QA-025`: produtos duplicados não geram alerta.
- `QA-036`: exportar vídeo sem queimar legendas ainda exige transcrição.
- `QA-037`: flag mestre de edição dinâmica é ignorada.
- `QA-039`: remapeamento após remover silêncio perde `Word` e seus timestamps.
- `QA-040`: margens negativas criam cortes fora do intervalo válido.
- `QA-041`: recriar telas/`VideoProject` perde formato, fonte, keywords e segmentos de movimento.
- `QA-043`: apóstrofo no caminho pode quebrar o filtro libass.
- `QA-044`: executável não assinado.
- `QA-045`: o site pode exibir `[object Object]` e `Failed to fetch` ao usuário.
- `QA-046`: fetch do cadastro/checkout não tem timeout/cancelamento e pode ficar carregando indefinidamente.
- `QA-047`: polling de ativação ignora `response.ok` e encerra tentativas mantendo mensagem de pendência.
- `QA-050`: recuperação de senha e login social são botões sem fluxo implementado.
- `QA-051`: lint falha com 19 diagnósticos e não está no CI principal.
- `QA-049` (baixo): landing publicada contém placeholder de demo, métrica provisória e depoimentos ilustrativos não validados.

### Ordem recomendada antes de qualquer lançamento

1. Corrigir e testar revogação/suspensão de acesso, máquina de estados financeiros, precedência/idempotência de webhooks e renovação de entitlements.
2. Isolar Trello por conta/quadro e tornar identidade/idempotência de posts globalmente estável.
3. Impedir exportações/encartes parcialmente corretos, cache antigo, sobrescrita e escritores concorrentes.
4. Tornar jobs de vídeo vinculados a uma versão imutável do projeto e preservar texto/timestamps/configuração.
5. Alinhar oferta comercial ao contrato Asaas realmente enviado.
6. Adicionar regressões em PostgreSQL e E2E controlado com Asaas sandbox, Trello descartável, Photoshop real e Windows limpo.

Não confundir sucesso de build com prontidão funcional. Até esses bloqueadores serem resolvidos e validados, tratar o repositório como pré-produção.

## 18. Estado atual após a correção do baseline (2026-09-05)

O código foi alterado para tratar os 51 achados do relatório. O histórico da seção 17 continua útil para reproduções, mas as afirmações de que cada bug ainda existe não refletem mais o workspace atual.

### Correções implementadas

- Auth/licença (`QA-001` a `QA-007`): logout remoto idempotente, expiração de tokens de dispositivo, bloqueio de conta inativa, limite persistente de tentativas, fallback restritivo para plano inválido, verificação online de plano pago, checagem de assinatura/período em rotas protegidas e máquina de estados de webhook com data/precedência que restaura entitlements em renovação.
- Checkout/IA (`QA-008` a `QA-014`): `Idempotency-Key` do navegador até o Asaas, validação de respostas externas, timeout OAuth, validação forte de cadastro, reserva atômica/devolução de crédito e normalização semântica dos cortes retornados pela OpenAI.
- Isolamento/dados (`QA-015` a `QA-018`): segredos Trello por conta, banco legado não é entregue automaticamente a conta moderna, seletores usam ID mesmo com homônimos, validação no repositório e `operation_id` único para reenvio idempotente de criação.
- PDF (`QA-019` a `QA-021`): detalhes completos, células com `Paragraph` para wrap/entidades e nomes de saída com cliente/timestamp; escrita usa arquivo temporário e substituição final.
- Encartes (`QA-022` a `QA-027`): as correções foram implementadas inicialmente, mas a funcionalidade completa, seus módulos e dependências foram removidos posteriormente do produto.
- Editor de vídeo: além da detecção/configuração e abertura segura do DaVinci, existe um instalador de painel. O painel analisa silêncios com FFmpeg, reconstrói uma nova timeline pelos trechos falados e chama um worker local Faster-Whisper para gerar SRT sincronizado sem exigir Resolve Studio. Confirmações e resultados são exibidos por `davinci_dialog.py` em uma janela externa com o tema do aplicativo; a caixa nativa é fallback. O motor anterior permanece parcialmente sem navegação.
- Trello (`QA-028` a `QA-030`): marcador inclui origem conta/banco, cache e vínculo do card incluem o quadro, registros antigos são reconciliados pelo marcador e criação de card possui trava compartilhada dentro do processo. A garantia absoluta entre dois processos ainda depende de validação/estratégia no provedor.
- Vídeo (`QA-031` a `QA-043`): edição invalida palavras antigas, segmentação usa timestamps reais, jobs são vinculados ao projeto/origem, análise de silêncio é consumida e restaurada só ao falhar, writer único, destinos únicos, exportação sem legenda, flag mestre de efeitos, timeouts/limpeza, preservação de palavras/configurações, validação de margens, filter script para comandos grandes e temporário ASS opaco para caminhos com apóstrofo.
- Distribuição/site (`QA-044` a `QA-051`): release com tag falha sem certificado e valida Authenticode; mensagens de API são normalizadas; fetch/polling possuem timeout/status; a oferta agora é somente mensal sem trial; foram removidos depoimentos/métrica/placeholders e ações sociais/recuperação falsas; lint/build do site entraram no CI.
- O executável passou a gravar exportações em `%LOCALAPPDATA%\NeivaPlanner\exports`, evitando tentativa de escrita em `Program Files`.

### Estado dos testes

- `python -m compileall -q content_planner ai_service tests`: passou.
- `.venv\Scripts\python.exe -m unittest discover -s tests -q`: 54/54 passaram em 2026-09-06 após a inclusão da base administrativa e recuperação de senha por configuração temporária.
- `npm run lint` em `neiva-site`: passou para `app/` e componentes publicados.
- `npm run build` em `neiva-site`: passou; Vinext ainda informa apenas que a classificação estática da rota é desconhecida.
- `git diff --check`: passou.

### Pendências que não podem ser encerradas apenas com o código local

- Executar Asaas sandbox ponta a ponta, incluindo compra, duplicação, vencimento, cancelamento, estorno, chargeback, renovação e eventos simultâneos em PostgreSQL/múltiplos workers.
- Executar OAuth/criação concorrente em um quadro Trello descartável. A trava de cards é por processo; o Trello não oferece idempotency key equivalente neste fluxo.
- Validar a resposta e a qualidade editorial com OpenAI real, sem usar credencial de produção.
- Validar em uma instalação real do DaVinci Resolve gratuito: instalação/atualização do painel, abertura/foco das janelas temáticas, fallback nativo, menu Scripts, download inicial do Whisper `small`, importação de SRT no Media Pool, arraste para subtitle track, mídia offline, vídeo longo, áudio sem fala, limites de frame em 23.976/29.97 e criação A/V por `CreateTimelineFromClips`.
- Fazer inspeção visual integral dos PDFs e vídeos, incluindo mídia longa/4K, áudio ruim, disco cheio e encerramento no meio do job.
- Testar o novo EXE em Windows limpo e configurar certificado real nos secrets `SIGNING_CERTIFICATE_BASE64` e `SIGNING_CERTIFICATE_PASSWORD` antes de criar uma tag.
- Migrar a API para migrations versionadas (Alembic). `create_all` e ALTERs aditivos continuam sendo limitação arquitetural.
- Definir política operacional de suporte/recuperação de senha, backup/restauração, retenção/carência de assinatura e atualização/desinstalação. Os botões falsos foram removidos, mas um canal real de recuperação ainda é requisito operacional para clientes.

Até as integrações acima serem exercitadas em ambientes descartáveis, tratar Asaas e Trello como candidatos a release, não como fluxos certificados para produção.
