# Neiva Planner

Aplicativo desktop para planejar calendários editoriais, clientes, conteúdos, PDFs e cards no Trello. Os dados ficam somente neste computador, em um banco SQLite local.

O **Estúdio de Vídeo** reúne importação local, download autorizado do YouTube, transcrição com Faster-Whisper, busca de cortes, revisão de texto e exportação SRT/VTT ou MP4. O vídeo permanece carregado entre as etapas, evitando downloads e transcrições repetidos. Para esses recursos, instale o FFmpeg (incluindo `ffprobe`) e adicione sua pasta `bin` ao PATH.

A interface é adaptativa: em janelas estreitas, o menu lateral se recolhe e a navegação continua disponível por um seletor no topo. Em telas maiores, o menu lateral completo é restaurado automaticamente.

Em **Estúdio de Vídeo > Importar**, baixe vídeos públicos apenas quando você tiver direito ou autorização para fazê-lo. Os downloads são salvos em `exports/downloads` por padrão.

## Navegação

- **Dashboard**: resumo do conteúdo e atalhos principais.
- **Clientes**: cadastro, busca e manutenção dos clientes.
- **Planejamento**: calendário, cadastro de conteúdo, exportação de PDF e envio ao Trello na mesma tela.
- **Estúdio de Vídeo**: importação, legendas, cortes, edição e exportação.
- **Encarte de Ofertas**: automação de planilhas, fotos e modelos PSD.
- **Configurações**: credenciais e caminhos de armazenamento.

## Requisitos

- Windows 10 ou superior
- Python 3.10 ou superior (apenas para desenvolvimento)
- Adobe Photoshop instalado (para o módulo **Encarte de Ofertas**)

## Encarte de Ofertas

Em **Encarte de Ofertas**, importe uma planilha XLSX com colunas de descrição e valor/preço, associe uma pasta de fotos e preencha um modelo PSD pelo Photoshop. Também é possível extrair fotos de grupos `GRUPO01`, `GRUPO02` etc. e exportar PSDs para JPG/PDF.

O módulo é independente e já inclui a automação necessária. Não requer a pasta antiga da Automação Liderança.

## Executar em desenvolvimento

```powershell
cd "<pasta-do-repositorio>"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m content_planner
```

## Configuração e segurança

- Para usar recursos vinculados ao plano, crie uma conta e entre pelo aplicativo. A URL da API é definida pelo produto; a chave OpenAI permanece exclusivamente no servidor.
- A transcrição é local. Quando a opção **Usar IA OpenAI** estiver ativa, somente a transcrição com timestamps é enviada à API para selecionar os cortes; esse uso pode gerar custo.
- O executável de produção inclui FFmpeg e FFprobe. Em desenvolvimento, execute `powershell -ExecutionPolicy Bypass -File scripts\prepare_ffmpeg.ps1` ou disponibilize ambos no `PATH`.
- Para o módulo de encartes, instale o Adobe Photoshop. O projeto já contém toda a automação de PSD necessária.

Os vídeos baixados ficam em `exports/downloads` e os resultados das análises em `exports/analises_de_cortes` (JSON).

## Testar

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Gerar o executável

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean NeivaPlanner.spec
```

O arquivo final será `dist\NeivaPlanner_v1.exe`. No executável, bancos ficam em `%LOCALAPPDATA%\NeivaPlanner\database` e exportações em `%LOCALAPPDATA%\NeivaPlanner\exports`. Dados legados não são associados automaticamente a uma conta moderna; qualquer migração precisa confirmar o titular.

Antes de distribuir uma versão, execute os testes, gere o executável em uma pasta nova e valide manualmente: abertura do aplicativo, criação de cliente/post, exportação de PDF, conexão Trello e um vídeo curto.

O workflow diferencia o canal pelo formato da tag. Uma tag estável exata, como `v1.0.1`, exige os secrets `SIGNING_CERTIFICATE_BASE64` e `SIGNING_CERTIFICATE_PASSWORD`, assina e valida o EXE e publica uma release oficial. Uma tag com sufixo, como `v1.0.1-test.1`, `v1.0.1-beta.1` ou `v1.0.1-rc.1`, publica uma prerelease de teste sem assinatura. Tags `v*` fora desses formatos falham. O link público do site usa `releases/latest`, que ignora prereleases; para testar uma versão não assinada, baixe o artefato diretamente na página da prerelease correspondente.

Para distribuir os recursos de vídeo sem exigir configuração manual, coloque `ffmpeg.exe` e `ffprobe.exe` em `assets\ffmpeg` antes de gerar o executável. Se esses arquivos não estiverem presentes, o aplicativo procurará o FFmpeg no `PATH` do Windows.

O script `scripts\prepare_ffmpeg.ps1` baixa a versão fixada do build Windows, confere seu SHA-256 e prepara os binários e documentos de licença. O build utilizado é distribuído sob GPLv3; a licença, a configuração do build e o link do código-fonte correspondente são incorporados ao aplicativo em `assets\ffmpeg`.

## Trello

Em **Configurações**, o usuário clica em **Conectar ao Trello**, autoriza o Neiva Planner no navegador e escolhe o quadro pelo nome. O OAuth Secret permanece somente na API rafaau. O token individual e o ID do quadro são entregues uma única vez ao aplicativo autenticado e salvos no cofre do Windows; o programa nunca recebe a senha do usuário.

### Preparar o login do Trello para distribuição

Esta configuração é feita uma única vez pelo responsável pelo Neiva Planner, não pelo cliente:

1. Crie ou abra o Power-Up do Neiva Planner em `https://trello.com/apps/admin` e gere a API Key e o OAuth Secret.
2. Nas origens permitidas, adicione `https://neiva-ai-api.onrender.com`.
3. No serviço da API no Render, configure `TRELLO_API_KEY` e `TRELLO_API_SECRET` como variáveis secretas.
4. Se a API usar outro domínio, configure também `PUBLIC_API_URL`; o callback será `<PUBLIC_API_URL>/v1/integrations/trello/callback`.

O OAuth Secret nunca deve ser incluído no Git ou no executável. A API usa o segredo apenas para assinar o OAuth 1.0 e criptografa as credenciais temporárias enquanto o navegador conclui o fluxo.

O sistema só envia ao Trello conteúdos que ainda não possuem um card vinculado. Assim, repetir o envio não cria cards duplicados.

Cada card recebe um identificador interno do post local. Caso a conexão caia após o Trello aceitar uma criação, uma nova tentativa procura esse identificador antes de criar outro card.

## Backup

Em desenvolvimento, faça cópias periódicas de `database\content_planner.db` e de `database\accounts`. No executável, copie `%LOCALAPPDATA%\NeivaPlanner\database`, incluindo `accounts\<id>\content_planner.db`. Esses arquivos contêm clientes e conteúdos; credenciais ficam separadamente no cofre do Windows.
