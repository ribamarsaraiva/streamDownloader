"""
deps.py — Verificacao e auto-instalacao de dependencias.

Responsavel por garantir que PySide6, yt-dlp e FFmpeg estejam disponiveis
antes de a interface subir. Projetado para Windows (auto-download do FFmpeg),
mas funciona tambem em Linux/macOS para desenvolvimento.

Nenhuma dependencia externa e importada no topo deste arquivo de proposito:
ele precisa ser capaz de rodar num Python "cru" e instalar o que falta.
"""

from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable, Optional

# Diretorio base do app (funciona tanto rodando .py quanto empacotado com PyInstaller)
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

BIN_DIR = APP_DIR / "bin"

# Pacotes pip: nome_de_import -> especificacao_pip
PIP_PACKAGES = {
    "PySide6": "PySide6>=6.5",
    "yt_dlp": "yt-dlp",
    "certifi": "certifi",
}

# Build oficial do FFmpeg para Windows (gyan.dev — essentials, menor).
FFMPEG_WINDOWS_URL = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)

# Tipo do callback de log/progresso (mensagem -> None)
LogFn = Callable[[str], None]


def _default_log(msg: str) -> None:
    print(msg, flush=True)


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


# --------------------------------------------------------------------------- #
# Pacotes pip
# --------------------------------------------------------------------------- #
def _is_module_installed(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def _is_store_python() -> bool:
    """Detecta o Python instalado pela Microsoft Store (caminhos problematicos)."""
    exe = sys.executable.lower()
    return "windowsapps" in exe or "microsoft\\windowsapps" in exe or "packages\\pythonsoftwarefoundation" in exe


def _long_paths_enabled() -> bool:
    """Verifica no registro se o suporte a caminhos longos esta ligado (Windows)."""
    if not is_windows():
        return True
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
            return bool(value)
    except Exception:  # noqa: BLE001
        return False


def _ensure_pip(log: LogFn) -> None:
    """Garante que o pip esteja disponivel via ensurepip, se necessario."""
    if importlib.util.find_spec("pip") is not None:
        return
    log("pip nao encontrado; tentando habilitar com ensurepip ...")
    try:
        subprocess.run(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        log(f"Nao foi possivel executar ensurepip: {exc}")


def _diagnose_pip_failure(output: str, spec: str, log: LogFn) -> None:
    """Interpreta a saida do pip e imprime orientacoes acionaveis."""
    low = output.lower()

    long_path_issue = (
        "long path" in low
        or "enable-long-paths" in low
        or ("oserror" in low and "no such file or directory" in low)
    )

    if long_path_issue:
        log("")
        log(">> CAUSA PROVAVEL: suporte a CAMINHOS LONGOS desabilitado no Windows.")
        log("   O PySide6 tem arquivos com caminhos muito longos e o Windows")
        log("   bloqueia caminhos acima de 260 caracteres por padrao.")
        log("")
        log("   COMO RESOLVER (escolha UMA opcao):")
        log("   [A] Habilitar caminhos longos (PowerShell como ADMINISTRADOR):")
        log('       Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem" '
            '-Name "LongPathsEnabled" -Value 1')
        log("       ...e REINICIE o computador. Depois rode de novo.")
        log("")
        if _is_store_python():
            log("   [B] Trocar o Python da Microsoft Store pelo oficial:")
            log("       - Desinstale o Python da Store.")
            log("       - Instale de https://www.python.org/downloads/ (marque")
            log('         "Add python.exe to PATH" e "Disable path length limit").')
        return

    if _is_store_python():
        log("")
        log(">> OBS: voce esta usando o Python da Microsoft Store, que costuma")
        log("   causar problemas de permissao e caminho. Se o erro persistir,")
        log("   instale o Python oficial de https://www.python.org/downloads/")


def _pip_install(spec: str, log: LogFn) -> bool:
    """Instala/atualiza um pacote via pip no interpretador atual."""
    log(f"Instalando {spec} ...")
    _ensure_pip(log)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", spec],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return True

        # Falhou: mostra a saida completa e diagnostica
        output = (proc.stdout or "") + (proc.stderr or "")
        log(f"ERRO ao instalar {spec} (codigo {proc.returncode}).")
        tail = "\n".join(output.strip().splitlines()[-15:])
        if tail:
            log("--- saida do pip (final) ---")
            log(tail)
            log("----------------------------")
        _diagnose_pip_failure(output, spec, log)
        return False
    except FileNotFoundError:
        log("ERRO: pip nao encontrado neste ambiente Python (nem via ensurepip).")
        return False


def ensure_pip_packages(log: LogFn = _default_log) -> bool:
    """Garante que todos os pacotes pip necessarios estejam instalados."""
    ok = True
    for import_name, spec in PIP_PACKAGES.items():
        if _is_module_installed(import_name):
            log(f"OK: {import_name} ja instalado.")
            continue
        log(f"Faltando: {import_name}.")
        if not _pip_install(spec, log):
            ok = False
    return ok


def update_ytdlp(log: LogFn = _default_log) -> None:
    """Mantem o yt-dlp atualizado — sites mudam com frequencia."""
    log("Atualizando yt-dlp ...")
    _pip_install("yt-dlp", log)


def update_certifi(log: LogFn = _default_log) -> None:
    """
    Mantem o certifi atualizado. O yt-dlp usa o certifi (quando instalado) para
    validar certificados HTTPS; um bundle de CAs antigo pode causar
    CERTIFICATE_VERIFY_FAILED em sites que trocaram de CA (ex.: X/Twitter).
    """
    log("Atualizando certifi (certificados HTTPS) ...")
    _pip_install("certifi", log)


# --------------------------------------------------------------------------- #
# FFmpeg
# --------------------------------------------------------------------------- #
def find_ffmpeg() -> Optional[str]:
    """
    Localiza o executavel do ffmpeg. Ordem de busca:
      1. binario embutido pelo PyInstaller (sys._MEIPASS/bin)
      2. pasta local ./bin
      3. PATH do sistema
    Retorna o caminho ou None.
    """
    exe = "ffmpeg.exe" if is_windows() else "ffmpeg"

    # 1) Quando empacotado, o PyInstaller extrai os dados para _MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "bin" / exe
        if bundled.is_file():
            return str(bundled)

    local = BIN_DIR / exe
    if local.is_file():
        return str(local)

    found = shutil.which("ffmpeg")
    if found:
        return found

    return None


def _download_file(url: str, dest: Path, log: LogFn) -> bool:
    """Baixa um arquivo mostrando progresso simples."""
    import urllib.request

    log(f"Baixando FFmpeg de {url} ...")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 (URL fixa e confiavel)
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 256
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        log(f"  FFmpeg: {pct}% ({downloaded // (1024*1024)} MB)")
        return True
    except Exception as exc:  # noqa: BLE001
        log(f"ERRO ao baixar FFmpeg: {exc}")
        return False


def _extract_ffmpeg_from_zip(zip_path: Path, log: LogFn) -> bool:
    """
    Extrai apenas ffmpeg.exe/ffprobe.exe do zip do gyan.dev para ./bin,
    achatando a estrutura de pastas do arquivo.
    """
    wanted = ("ffmpeg.exe", "ffprobe.exe")
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                base = os.path.basename(member)
                if base in wanted:
                    log(f"Extraindo {base} ...")
                    with zf.open(member) as src, open(BIN_DIR / base, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        return (BIN_DIR / "ffmpeg.exe").is_file()
    except Exception as exc:  # noqa: BLE001
        log(f"ERRO ao extrair FFmpeg: {exc}")
        return False


def ensure_ffmpeg(log: LogFn = _default_log) -> Optional[str]:
    """
    Garante que o FFmpeg esteja disponivel.
    Se ja existir (local ou PATH), retorna o caminho.
    No Windows, baixa e instala localmente se faltar.
    Em outros SOs, orienta o usuario (nao auto-instala).
    Retorna o caminho do ffmpeg ou None.
    """
    existing = find_ffmpeg()
    if existing:
        log(f"OK: FFmpeg encontrado em {existing}")
        return existing

    if not is_windows():
        log(
            "FFmpeg nao encontrado. Neste SO instale manualmente "
            "(ex.: 'sudo apt install ffmpeg' ou 'brew install ffmpeg')."
        )
        return None

    # Windows: baixa build oficial e extrai para ./bin
    log("FFmpeg nao encontrado. Baixando build para Windows ...")
    zip_path = APP_DIR / "ffmpeg_download.zip"
    if not _download_file(FFMPEG_WINDOWS_URL, zip_path, log):
        return None
    if not _extract_ffmpeg_from_zip(zip_path, log):
        return None
    try:
        zip_path.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass

    return find_ffmpeg()


def get_bin_dir() -> Path:
    """Diretorio onde os binarios locais (ffmpeg) ficam."""
    return BIN_DIR


# --------------------------------------------------------------------------- #
# Orquestracao
# --------------------------------------------------------------------------- #
def ensure_all(log: LogFn = _default_log) -> dict:
    """
    Verifica e instala tudo. Retorna um dicionario com o estado:
      {"pip_ok": bool, "ffmpeg": Optional[str]}
    """
    log("== Verificando dependencias ==")

    # Quando empacotado como .exe (PyInstaller), as dependencias Python ja estao
    # embutidas: nao existe pip nem interpretador para instalar nada. So
    # garantimos o FFmpeg (que continua sendo um binario externo).
    if getattr(sys, "frozen", False):
        log("Modo empacotado (.exe): dependencias Python ja embutidas.")
        ffmpeg_path = ensure_ffmpeg(log)
        log("== Verificacao concluida ==")
        return {"pip_ok": True, "ffmpeg": ffmpeg_path}

    # Aviso preventivo: no Windows, Long Path desabilitado quebra o PySide6.
    if is_windows() and not _long_paths_enabled():
        needs_pyside = not _is_module_installed("PySide6")
        if needs_pyside:
            log("")
            log(">> AVISO: suporte a caminhos longos parece DESABILITADO no Windows.")
            log("   A instalacao do PySide6 provavelmente vai falhar. Recomendado")
            log("   habilitar antes (PowerShell como ADMINISTRADOR) e REINICIAR:")
            log('   Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem" '
                '-Name "LongPathsEnabled" -Value 1')
            log("")

    pip_ok = ensure_pip_packages(log)

    # Garante o certifi atualizado: o yt-dlp o usa para validar HTTPS e um
    # bundle antigo/ausente causa CERTIFICATE_VERIFY_FAILED (comum no X/Twitter).
    if _is_module_installed("certifi"):
        update_certifi(log)

    # Mantem o yt-dlp atualizado: sites como Facebook/X mudam o markup com
    # frequencia e um extractor antigo causa "Cannot parse data".
    if _is_module_installed("yt_dlp"):
        update_ytdlp(log)

    ffmpeg_path = ensure_ffmpeg(log)
    log("== Verificacao concluida ==")
    return {"pip_ok": pip_ok, "ffmpeg": ffmpeg_path}


if __name__ == "__main__":
    result = ensure_all()
    print("\nResultado:", result)
