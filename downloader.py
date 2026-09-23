"""
downloader.py — Logica de extracao e download usando yt-dlp.

Expoe:
  - list_formats(url): retorna metadados + lista de OPCOES SIMPLIFICADAS
  - download(url, option, dest_dir, ffmpeg_path, progress_cb): baixa a opcao escolhida

As "opcoes simplificadas" escondem a complexidade das faixas separadas de
video/audio do YouTube. Cada opcao carrega um 'format_selector' que sabemos
funcionar com o yt-dlp.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import yt_dlp


def _ssl_ydl_opts() -> dict:
    """
    Opcoes de SSL para o yt-dlp.

    A configuracao do bundle de CAs (certifi) e feita globalmente em
    sslfix.apply(), via SSL_CERT_FILE e o contexto SSL padrao do Python — o
    yt-dlp respeita ambos. Aqui tratamos apenas o fallback opcional:

    - Se SD_NO_CHECK_CERT=1, desativa a verificacao de certificado (ultimo
      recurso; INSEGURO, mas util atras de proxies corporativos que reescrevem
      o TLS e nao ha como instalar a CA interna).
    """
    if os.environ.get("SD_NO_CHECK_CERT") == "1":
        return {"nocheckcertificate": True}
    return {}


# Navegadores aceitos pelo yt-dlp para extrair cookies de sessao.
_SUPPORTED_BROWSERS = {
    "chrome", "chromium", "edge", "firefox", "brave", "opera", "vivaldi", "safari",
}


def _cookies_ydl_opts() -> dict:
    """
    Opcoes de cookies para o yt-dlp.

    Muitos videos (Facebook, Instagram, X) exigem uma sessao logada. O yt-dlp
    pode reutilizar os cookies do seu navegador. Ative definindo a variavel de
    ambiente SD_BROWSER com o nome do navegador onde voce esta logado, ex.:

        set SD_BROWSER=chrome     (ou edge, firefox, brave, opera, vivaldi)

    Retorna {} se nao configurado ou se o navegador nao for reconhecido.
    """
    browser = (os.environ.get("SD_BROWSER") or "").strip().lower()
    if browser in _SUPPORTED_BROWSERS:
        # O yt-dlp espera uma tupla; o 1o item e o nome do navegador.
        return {"cookiesfrombrowser": (browser,)}
    return {}


def _net_ydl_opts() -> dict:
    """Junta as opcoes de rede (SSL + cookies) usadas em toda chamada ao yt-dlp."""
    opts = {}
    opts.update(_ssl_ydl_opts())
    opts.update(_cookies_ydl_opts())
    return opts


def _friendly_error(exc: Exception, url: str) -> str:
    """
    Traduz erros comuns do yt-dlp em mensagens acionaveis, preservando o
    texto original ao final para diagnostico.
    """
    raw = str(exc)
    low = raw.lower()
    hint = ""

    if "cannot parse data" in low or "unable to extract" in low or "no video formats" in low:
        hint = (
            "O yt-dlp nao conseguiu ler os dados do video. Causas comuns:\n"
            "  - O video e PRIVADO ou exige LOGIN (o site mostrou um 'login "
            "wall'). Videos do Facebook/Instagram quase sempre exigem login.\n"
            "    SOLUCAO: use os cookies do seu navegador. Feche o app, defina "
            "a variavel e reabra:\n"
            "        set SD_BROWSER=chrome   (ou edge, firefox, brave)\n"
            "        python main.py\n"
            "  - O extractor do site pode estar temporariamente quebrado (bug "
            "conhecido do yt-dlp para Facebook). Rode: pip install --upgrade "
            "yt-dlp\n"
            "  - Se o link e de compartilhamento (facebook.com/share/... ou "
            "encurtado), abra no navegador e copie a URL final do video (com "
            "/watch/?v=, /reel/ ou /videos/)."
        )
    elif "certificate_verify_failed" in low or "certificate verify failed" in low:
        hint = (
            "Falha na verificacao do certificado SSL. Rode: "
            "pip install --upgrade certifi. Se estiver atras de proxy/antivirus "
            "corporativo, defina SD_NO_CHECK_CERT=1 como ultimo recurso."
        )
    elif "login" in low or "sign in" in low or "private" in low or "not available" in low:
        hint = (
            "O video parece exigir login ou nao esta disponivel publicamente. "
            "Verifique se o link abre no navegador sem estar logado."
        )
    elif "unsupported url" in low:
        hint = "Este link nao e suportado pelo yt-dlp (ou nao aponta para um video)."

    if hint:
        return f"{hint}\n\n[Detalhe tecnico: {raw}]"
    return raw


@dataclass
class SimpleOption:
    """Uma opcao amigavel exibida ao usuario."""
    label: str                 # ex.: "1080p (video+audio)"
    format_selector: str       # ex.: "bv*[height<=1080]+ba/b[height<=1080]"
    kind: str                  # "video" ou "audio"
    ext_hint: str = "mp4"      # extensao final esperada
    res_tag: str = ""          # sufixo de resolucao p/ nome do arquivo (ex.: "1080p", "audio")
    extra_postprocessors: list = field(default_factory=list)


@dataclass
class VideoInfo:
    title: str
    duration: Optional[int]
    thumbnail: Optional[str]
    webpage_url: str
    options: List[SimpleOption]
    is_playlist: bool = False   # True se a URL era uma playlist (usamos o 1o item)


# Alturas de video que tentamos oferecer, da maior para a menor.
_TARGET_HEIGHTS = [2160, 1440, 1080, 720, 480, 360]


def _human_size(num_bytes: Optional[float]) -> str:
    if not num_bytes:
        return "?"
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def list_formats(url: str) -> VideoInfo:
    """
    Extrai metadados SEM baixar e monta opcoes simplificadas.
    Levanta excecao se a URL for invalida/inacessivel.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        **_net_ydl_opts(),
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(_friendly_error(exc, url)) from exc

    # Playlists: usa a primeira entrada por simplicidade
    is_playlist = False
    if info.get("_type") == "playlist" and info.get("entries"):
        is_playlist = True
        info = info["entries"][0]

    formats = info.get("formats", []) or []

    # Alturas de video realmente disponiveis neste video
    available_heights = sorted(
        {
            f.get("height")
            for f in formats
            if f.get("vcodec") not in (None, "none") and f.get("height")
        },
        reverse=True,
    )

    options: List[SimpleOption] = []

    def _track_size(f: dict) -> Optional[float]:
        # 1) tamanho reportado; 2) estimativa por bitrate (tbr em kbps) x duracao.
        size = f.get("filesize") or f.get("filesize_approx")
        if size:
            return float(size)
        tbr = f.get("tbr")  # kbps (kilobits/s)
        dur = info.get("duration")
        if tbr and dur:
            # tbr[kbps] * 1000 / 8 = bytes/s ; * duracao[s] = bytes
            return tbr * 1000 / 8 * dur
        return None

    # Melhor faixa de audio disponivel (usada em qualquer opcao de video+audio).
    _audio_tracks = [
        f for f in formats
        if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")
    ]
    _best_audio = max(_audio_tracks, key=lambda f: f.get("tbr") or 0, default=None)
    _audio_size = _track_size(_best_audio) if _best_audio else None

    # Estima o tamanho da opcao "video ate <=h", espelhando o seletor
    # bv*[height<=h]+ba: pega a MELHOR faixa de video com altura <= h (por
    # bitrate) e soma o melhor audio. Assim cada altura tem um valor distinto.
    def _est_size_for_height(h: int) -> Optional[float]:
        vids = [
            f for f in formats
            if f.get("vcodec") not in (None, "none")
            and f.get("height")
            and f.get("height") <= h
        ]
        # Prioriza a maior altura possivel (<=h); em empate, maior bitrate.
        v = max(
            vids,
            key=lambda f: (f.get("height") or 0, f.get("tbr") or 0),
            default=None,
        )
        vs = _track_size(v or {})
        # Se a faixa de video ja for progressiva (contem audio), nao soma audio.
        if v and v.get("acodec") not in (None, "none"):
            return vs
        if vs and _audio_size:
            return vs + _audio_size
        return vs or _audio_size

    for h in _TARGET_HEIGHTS:
        if available_heights and h > available_heights[0]:
            continue
        if h not in available_heights:
            # oferece mesmo assim se houver algo <= h (yt-dlp escolhe o proximo)
            if not any(ah <= h for ah in available_heights):
                continue
        size = _est_size_for_height(h)
        size_txt = f" ~{_human_size(size)}" if size else ""
        options.append(
            SimpleOption(
                label=f"{h}p (video+audio){size_txt}",
                format_selector=(
                    f"bv*[height<={h}]+ba/b[height<={h}]"
                ),
                kind="video",
                ext_hint="mp4",
                res_tag=f"{h}p",
                extra_postprocessors=[
                    {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
                ],
            )
        )

    # Remove duplicatas mantendo ordem (caso alturas colidam no fallback)
    seen = set()
    deduped = []
    for opt in options:
        if opt.label in seen:
            continue
        seen.add(opt.label)
        deduped.append(opt)
    options = deduped

    # Opcao "melhor disponivel" no topo, se houver video
    if available_heights:
        best_h = available_heights[0]
        options.insert(
            0,
            SimpleOption(
                label=f"Melhor disponivel ({best_h}p)",
                format_selector="bv*+ba/b",
                kind="video",
                ext_hint="mp4",
                res_tag=f"{best_h}p",
                extra_postprocessors=[
                    {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
                ],
            ),
        )

    # Opcao so-audio (MP3)
    if any(f.get("acodec") not in (None, "none") for f in formats):
        options.append(
            SimpleOption(
                label="Somente audio (MP3)",
                format_selector="ba/b",
                kind="audio",
                ext_hint="mp3",
                res_tag="audio",
                extra_postprocessors=[
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            )
        )

    return VideoInfo(
        title=info.get("title") or "video",
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        webpage_url=info.get("webpage_url") or url,
        options=options,
        is_playlist=is_playlist,
    )


# Callback de progresso: recebe dict {"status", "percent", "speed", "eta", "text"}
ProgressFn = Callable[[dict], None]


def download(
    url: str,
    option: SimpleOption,
    dest_dir: str,
    ffmpeg_path: Optional[str] = None,
    progress_cb: Optional[ProgressFn] = None,
) -> str:
    """
    Baixa a opcao escolhida para dest_dir.
    Retorna o caminho do arquivo final (melhor esforco).
    Levanta excecao em caso de erro.
    """
    import os as _os

    # Guarda dois caminhos:
    #   "download": nome da faixa baixada (extensao intermediaria, ex.: .webm)
    #   "final":    nome apos o pos-processamento (extensao real, ex.: .mp4/.mp3)
    final_path_holder = {"download": None, "final": None}

    def _progress_hook(d: dict) -> None:
        if progress_cb is None:
            return
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes") or 0
            percent = (downloaded / total * 100) if total else None
            progress_cb(
                {
                    "status": "downloading",
                    "percent": percent,
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                    "text": d.get("_percent_str", "").strip(),
                }
            )
        elif status == "finished":
            # Ainda e o arquivo intermediario; o pos-processamento vem depois.
            final_path_holder["download"] = d.get("filename")
            progress_cb({"status": "processing", "percent": 100, "text": "Processando..."})

    def _postprocessor_hook(d: dict) -> None:
        # Executado quando cada pos-processador (remux/merge/extract audio)
        # termina. O 'filepath'/'info_dict.filepath' aqui ja reflete a
        # extensao FINAL (ex.: .mp4 apos remux, .mp3 apos extrair audio).
        if d.get("status") != "finished":
            return
        info_dict = d.get("info_dict") or {}
        path = info_dict.get("filepath") or d.get("filepath")
        if path:
            final_path_holder["final"] = path

    # Inclui a resolucao escolhida no nome do arquivo (ex.: "Titulo [1080p].mp4").
    # O sufixo e sanitizado para nao conflitar com o template do yt-dlp.
    tag = option.res_tag.strip()
    if tag:
        outtmpl = _os.path.join(dest_dir, f"%(title)s [{tag}].%(ext)s")
    else:
        outtmpl = _os.path.join(dest_dir, "%(title)s.%(ext)s")

    ydl_opts = {
        "format": option.format_selector,
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [_progress_hook],
        "postprocessor_hooks": [_postprocessor_hook],
        "postprocessors": list(option.extra_postprocessors),
        **_net_ydl_opts(),
    }
    if ffmpeg_path:
        # yt-dlp espera o DIRETORIO onde ffmpeg/ffprobe estao. Se recebermos o
        # caminho do executavel, usamos a pasta que o contem.
        if _os.path.isfile(ffmpeg_path):
            ydl_opts["ffmpeg_location"] = _os.path.dirname(ffmpeg_path)
        else:
            ydl_opts["ffmpeg_location"] = ffmpeg_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Preferencia de resolucao do caminho final, do mais confiavel ao menos:
        #   1. hook de pos-processamento (extensao real)
        #   2. filepath no info_dict (yt-dlp recente preenche apos PP)
        #   3. prepare_filename ajustado para a extensao de destino da opcao
        #   4. nome do arquivo baixado (intermediario)
        final = final_path_holder["final"] or info.get("filepath")
        if not final:
            try:
                base = ydl.prepare_filename(info)
                # Ajusta a extensao para a de destino da opcao (ex.: mp4/mp3),
                # ja que prepare_filename pode devolver a extensao intermediaria.
                root, _ext = _os.path.splitext(base)
                final = f"{root}.{option.ext_hint}"
            except Exception:  # noqa: BLE001
                final = final_path_holder["download"]

    if progress_cb:
        progress_cb({"status": "done", "percent": 100, "text": "Concluido"})

    return final or final_path_holder["download"] or dest_dir


if __name__ == "__main__":
    # Teste rapido de linha de comando: python downloader.py <url>
    import sys

    if len(sys.argv) < 2:
        print("Uso: python downloader.py <url>")
        raise SystemExit(1)

    vi = list_formats(sys.argv[1])
    print(f"\nTitulo: {vi.title}")
    print(f"Duracao: {vi.duration}s")
    print("\nOpcoes:")
    for i, opt in enumerate(vi.options):
        print(f"  [{i}] {opt.label}  -> {opt.format_selector}")
