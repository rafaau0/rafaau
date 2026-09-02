# Neiva Planner

Aplicativo desktop para planejar calendários editoriais, clientes, conteúdos, PDFs e cards no Trello. Os dados ficam somente neste computador, em um banco SQLite local.

Também inclui **Legendas de Vídeo**: transcrição local com Faster-Whisper, revisão de texto, exportação SRT/VTT e MP4 com legendas incorporadas. Para esse recurso, instale o FFmpeg (incluindo `ffprobe`) e adicione sua pasta `bin` ao PATH.

A interface é adaptativa: em janelas estreitas, o menu lateral se recolhe e a navegação continua disponível por um seletor no topo. Em telas maiores, o menu lateral completo é restaurado automaticamente.

Em **Baixar YouTube**, baixe vídeos públicos apenas quando você tiver direito ou autorização para fazê-lo. Os downloads são salvos em `exports/downloads` por padrão. O FFmpeg é recomendado para combinar vídeo e áudio na melhor qualidade.

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

- Para **Encontrar Cortes com IA**, crie uma chave na OpenAI, configure o faturamento da conta e informe-a em **Configurações > OPENAI_API_KEY**. A chave é salva no cofre do Windows e nunca deve ser adicionada ao Git, compartilhada por mensagem ou colocada no código.
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

O arquivo final será `dist\NeivaPlanner.exe`. Ao abrir o executável, as pastas `database` e `exports` são criadas ao lado dele.

## Trello

Em **Configurações**, informe a chave da API, token e ID do quadro. As credenciais são salvas no banco local deste computador; faça backup dele com cuidado e não o compartilhe publicamente.

O sistema só envia ao Trello conteúdos que ainda não possuem um card vinculado. Assim, repetir o envio não cria cards duplicados.

## Backup

Faça cópias periódicas de `database\content_planner.db`. Esse arquivo contém os clientes, conteúdos e configurações do aplicativo.
