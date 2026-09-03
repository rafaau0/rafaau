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
cd "C:\Users\rafaa\Documents\PROJETOS\Neiva-Planner-main"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m content_planner
```

## Configuração e segurança

- Para **Estúdio de Vídeo > Cortes** com IA, crie uma chave na OpenAI, configure o faturamento da conta e informe-a em **Configurações > OPENAI_API_KEY**. A chave é salva no cofre do Windows e nunca deve ser adicionada ao Git, compartilhada por mensagem ou colocada no código.
- A transcrição é local. Quando a opção **Usar IA OpenAI** estiver ativa, somente a transcrição com timestamps é enviada à API para selecionar os cortes; esse uso pode gerar custo.
- Instale o [FFmpeg](https://ffmpeg.org/) e deixe `ffmpeg` e `ffprobe` disponíveis no `PATH` para download/transcrição de vídeo.
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

O arquivo final será `dist\NeivaPlanner_v1.exe`. No executável, o banco é salvo em `%LOCALAPPDATA%\NeivaPlanner\database`; bancos de versões portáteis anteriores são migrados automaticamente. Os arquivos exportados continuam na pasta `exports` ao lado do executável.

Antes de distribuir uma versão, execute os testes, gere o executável em uma pasta nova e valide manualmente: abertura do aplicativo, criação de cliente/post, exportação de PDF, conexão Trello e um vídeo curto. Assine o executável antes de distribuição pública.

Para distribuir os recursos de vídeo sem exigir configuração manual, coloque `ffmpeg.exe` e `ffprobe.exe` em `assets\ffmpeg` antes de gerar o executável. Se esses arquivos não estiverem presentes, o aplicativo procurará o FFmpeg no `PATH` do Windows.

## Trello

Em **Configurações**, o usuário clica em **Conectar ao Trello**, autoriza o Neiva Planner no navegador e escolhe o quadro pelo nome. O token e o ID do quadro são salvos no cofre do Windows, separados do banco local; o programa nunca recebe a senha do usuário.

### Preparar o login do Trello para distribuição

Esta configuração é feita uma única vez pelo responsável pelo Neiva Planner, não pelo cliente:

1. Crie ou abra o Power-Up do Neiva Planner em `https://trello.com/apps/admin` e gere a API Key.
2. Nas origens permitidas da chave, adicione `http://localhost:8765`.
3. Copie `assets\trello_app.example.json` para `assets\trello_app.json`.
4. Substitua o valor de `api_key` pela chave pública do Power-Up.
5. Gere novamente o executável. O arquivo real é ignorado pelo Git e incorporado somente ao build.

Também é possível definir `TRELLO_APP_KEY` no ambiente de build. A chave do aplicativo é pública; o token individual de cada usuário permanece secreto no cofre do Windows.

O sistema só envia ao Trello conteúdos que ainda não possuem um card vinculado. Assim, repetir o envio não cria cards duplicados.

Cada card recebe um identificador interno do post local. Caso a conexão caia após o Trello aceitar uma criação, uma nova tentativa procura esse identificador antes de criar outro card.

## Backup

Em desenvolvimento, faça cópias periódicas de `database\content_planner.db`. No executável, copie `%LOCALAPPDATA%\NeivaPlanner\database\content_planner.db`. Esse arquivo contém clientes e conteúdos; as credenciais ficam separadamente no cofre do Windows.
