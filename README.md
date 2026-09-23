# Stream Downloader

App desktop para baixar videos de sites como YouTube, X (Twitter), Instagram e
Facebook. Voce cola o link, escolhe um formato simplificado, seleciona a pasta
de destino e baixa. Usa [yt-dlp](https://github.com/yt-dlp/yt-dlp) como motor e
[FFmpeg](https://ffmpeg.org/) para juntar audio/video.

## Como funciona

```
Colar link  ->  Analisar  ->  Escolher formato  ->  Escolher pasta  ->  Baixar
```

- **Analise**: o yt-dlp le os metadados do video (sem baixar) e o app monta
  opcoes amigaveis: "Melhor disponivel", "1080p", "720p", ..., "Somente audio (MP3)".
- **Download**: o yt-dlp baixa as faixas e o FFmpeg junta audio+video (ou
  converte para MP3), salvando na pasta escolhida.

## Requisitos

- **Windows** (o app baixa o FFmpeg automaticamente para Windows).
- **Python 3.9+** instalado ([python.org](https://www.python.org/downloads/) —
  marque "Add Python to PATH" no instalador).

As demais dependencias (PySide6, yt-dlp, FFmpeg) sao **verificadas e instaladas
automaticamente** na primeira execucao. O FFmpeg vai para uma subpasta `bin/`
do proprio app — nao precisa de permissao de administrador.

## Como usar (Windows)

1. Instale o Python 3.9+ (se ainda nao tiver).
2. Baixe/coloque esta pasta em qualquer lugar.
3. Duplo-clique em `main.py`, ou pelo terminal:

   ```bat
   python main.py
   ```

4. Na primeira vez, aguarde a instalacao automatica das dependencias.
5. Cole o link, clique **Analisar**, escolha o formato, escolha a pasta e clique **Baixar**.

## Estrutura

```
streamDownloader/
├── main.py          # ponto de entrada: verifica deps e sobe a interface
├── deps.py          # verificacao e auto-instalacao (PySide6, yt-dlp, FFmpeg)
├── downloader.py    # logica com yt-dlp (listar formatos, baixar)
├── ui.py            # interface desktop PySide6
├── requirements.txt
└── bin/             # ffmpeg.exe (criado automaticamente na 1a execucao)
```

## Gerar um executavel portatil (opcional)

Para distribuir como um unico `.exe` (sem exigir Python instalado):

```bat
pip install pyinstaller
pyinstaller --onefile --windowed --name StreamDownloader main.py
```

O executavel sai em `dist/StreamDownloader.exe`. O FFmpeg continua sendo baixado
para a pasta `bin/` ao lado do executavel na primeira execucao.

## Observacoes

- **yt-dlp desatualizado**: sites mudam com frequencia. Se um download falhar,
  rode `pip install --upgrade yt-dlp`. (O app tambem tenta manter atualizado.)
- **Legalidade**: baixar videos pode violar os Termos de Servico dos sites e
  envolver direitos autorais. Use para conteudo proprio, uso pessoal/educacional
  ou material com licenca que permita.

## Solucao de problemas

| Problema | Causa provavel | Solucao |
|---|---|---|
| "python nao e reconhecido" | Python fora do PATH | Reinstale marcando "Add Python to PATH" |
| Download de alta qualidade falha | FFmpeg ausente | Deixe o app baixar (precisa de internet) ou instale o FFmpeg |
| Erro de extracao num site | yt-dlp desatualizado | `pip install --upgrade yt-dlp` |
| `Cannot parse data` (Facebook/Instagram) | Video exige login OU bug temporario do extractor do yt-dlp | Use os cookies do navegador: `set SD_BROWSER=chrome` (ou edge/firefox) antes de abrir o app. Se persistir, atualize o yt-dlp; pode ser bug conhecido do site |
| `CERTIFICATE_VERIFY_FAILED` / "unable to get local issuer certificate" | Python nao acha os certificados raiz (comum no Windows ou atras de antivirus/proxy corporativo) | O app ja usa o `certifi` automaticamente. Se persistir (proxy que reescreve TLS), rode como ultimo recurso com a verificacao desativada: defina a variavel `SD_NO_CHECK_CERT=1` antes de abrir o app (inseguro) |

### Erro de certificado SSL (Windows)

Se ao analisar um link aparecer `CERTIFICATE_VERIFY_FAILED`, o app agora
resolve automaticamente usando o pacote `certifi` (certificados da Mozilla).

Se o erro persistir — normalmente por um proxy/antivirus corporativo que
intercepta o trafego HTTPS — o ideal e instalar a CA interna da empresa no
Windows. Como ultimo recurso (e por sua conta e risco, pois desativa a
validacao do certificado), rode com:

```bat
set SD_NO_CHECK_CERT=1
python main.py
```
