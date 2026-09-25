# -*- mode: python ; coding: utf-8 -*-
"""
StreamDownloader.spec — receita de build do PyInstaller.

Gera um unico executavel (onefile) sem console (janela GUI), com FFmpeg
embutido. O .exe NAO baixa nada na primeira execucao: so executa.

Como usar (recomendado):
    build_exe.bat

Ou manualmente:
    1. Coloque ffmpeg.exe e ffprobe.exe em ./bin/
       (rode uma vez: python -c "import deps; deps.ensure_ffmpeg()")
    2. pip install pyinstaller
    3. pyinstaller StreamDownloader.spec

O executavel sai em dist/StreamDownloader.exe.
"""

from PyInstaller.utils.hooks import collect_all
import os

datas = []
binaries = []
hiddenimports = []

# certifi: garante o bundle de CAs dentro do exe.
for pkg in ("certifi",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# yt-dlp usa muitos extractors carregados dinamicamente: colete tudo.
d, b, h = collect_all("yt_dlp")
datas += d
binaries += b
hiddenimports += h

# --- EMBUTIR o ffmpeg.exe/ffprobe.exe (obrigatorio para exe sem download) ---
_missing = []
for _exe in ("ffmpeg.exe", "ffprobe.exe"):
    _p = os.path.join("bin", _exe)
    if os.path.isfile(_p):
        binaries.append((_p, "bin"))
        print(f"[spec] OK: embutindo {_p}")
    else:
        _missing.append(_p)
        print(f"[spec] ERRO: {_p} nao encontrado.")

if _missing:
    print()
    print("[spec] ============================================================")
    print("[spec] FFmpeg NAO encontrado em ./bin/")
    print("[spec] O executavel NAO sera autonomo (vai tentar baixar na 1a vez).")
    print("[spec] Para embutir:")
    print("[spec]   1. Rode: python -c \"import deps; deps.ensure_ffmpeg()\"")
    print("[spec]   2. Ou baixe o essentials de https://www.gyan.dev/ffmpeg/")
    print("[spec]      e copie ffmpeg.exe + ffprobe.exe para a pasta bin/")
    print("[spec]   3. Rode de novo: pyinstaller StreamDownloader.spec")
    print("[spec] ============================================================")
    print()

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="StreamDownloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI: sem janela de console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="app.ico",       # opcional: caminho de um icone .ico
)
