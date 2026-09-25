# Stream Downloader

App desktop para baixar videos de sites como YouTube, X (Twitter), Instagram e
Facebook. Voce cola o link, escolhe um formato simplificado, seleciona a pasta
de destino e baixa. Usa [yt-dlp](https://github.com/yt-dlp/yt-dlp) como motor e
[FFmpeg](https://ffmpeg.org/) para juntar audio/video.

## Como funciona

```
Colar link  ->  Analisar  ->  Escolher formato  ->  Escolher pasta  ->  Baixar
```

* **Analise**: o yt-dlp le os metadados do video (sem baixar) e o app monta
  opcoes amigaveis: "Melhor disponivel", "1080p", "720p", ..., "Somente audio (MP3)".
* **Download**: o yt-dlp baixa as faixas e o FFmpeg junta audio+video (ou
  converte para MP3), salvando na pasta escolhida.

## Opcao 1 — Executavel autonomo (recomendado para distribuir)

Gera um unico `.exe` que **nao precisa de Python**, **nao baixa FFmpeg** e
**nao instala pacotes** na primeira execucao. So executar.

No Windows, com Python 3.9+ instalado (so para o build):

```bat
build_exe.bat
```

O script:
1. Instala as dependencias de build (PySide6, yt-dlp, certifi, pyinstaller).
2. Baixa o FFmpeg **apenas nesta etapa de build** (se ainda nao estiver em `bin/`).
3. Gera `dist\StreamDownloader.exe` com FFmpeg embutido.

Copie so o `.exe` para qualquer PC Windows e rode. Internet so e necessaria
para baixar os videos (nao para dependencias).

### Build manual (equivalente)

```bat
pip install -r requirements.txt pyinstaller
python -c "import deps; deps.ensure_ffmpeg()"
pyinstaller StreamDownloader.spec
```

## Opcao 2 — Rodar com Python (desenvolvimento)

1. Instale o Python 3.9+ ([python.org](https://www.python.org/downloads/) —
   marque "Add Python to PATH").
2. Coloque esta pasta em qualquer lugar.
3. Rode:

```bat
python main.py
```

Na primeira vez o app instala PySide6, yt-dlp e baixa o FFmpeg para `bin/`
(precisa de internet). Nas proximas, sobe direto.

## Estrutura

```
streamDownloader/
├── main.py              # ponto de entrada
├── deps.py              # deps + FFmpeg (nao baixa no modo .exe)
├── downloader.py        # logica yt-dlp
├── ui.py                # interface PySide6
├── sslfix.py           # certificados HTTPS
├── requirements.txt
├── StreamDownloader.spec
├── build_exe.bat        # gera o .exe autonomo
└── bin/                 # ffmpeg.exe (criado no build ou na 1a execucao .py)
```

## Observacoes

* **yt-dlp desatualizado**: sites mudam com frequencia. No modo Python:
  `pip install --upgrade yt-dlp`. No .exe, reconstrua com yt-dlp atualizado.
* **Legalidade**: baixar videos pode violar os Termos de Servico dos sites e
  envolver direitos autorais. Use para conteudo proprio, uso pessoal/educacional
  ou material com licenca que permita.

## Solucao de problemas

| Problema | Causa provavel | Solucao |
| --- | --- | --- |
| "python nao e reconhecido" | Python fora do PATH | Reinstale marcando "Add Python to PATH" |
| Download de alta qualidade falha | FFmpeg ausente | No .exe: reconstrua com `build_exe.bat`. No .py: deixe o app baixar |
| Erro de extracao num site | yt-dlp desatualizado | `pip install --upgrade yt-dlp` e reconstrua o exe se for o caso |
| Cannot parse data (Facebook/Instagram) | Video exige login OU bug do extractor | `set SD_BROWSER=chrome` (ou edge/firefox) antes de abrir |
| CERTIFICATE_VERIFY_FAILED | certificados / proxy | O app usa certifi. Ultimo recurso: `set SD_NO_CHECK_CERT=1` |

### Erro de certificado SSL (Windows)

Se ao analisar um link aparecer `CERTIFICATE_VERIFY_FAILED`, o app resolve
automaticamente com o pacote `certifi`.

Se persistir (proxy/antivirus corporativo), como ultimo recurso:

```bat
set SD_NO_CHECK_CERT=1
StreamDownloader.exe
```
