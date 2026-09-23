# -*- mode: python ; coding: utf-8 -*-
"""
StreamDownloader.spec — receita de build do PyInstaller.

Gera um unico executavel (onefile) sem console (janela GUI).

Como usar:
    pip install pyinstaller
    pyinstaller StreamDownloader.spec

O executavel sai em dist/StreamDownloader.exe.

Observacoes:
- Os modulos locais (main, deps, downloader, ui, sslfix) sao incluidos como
  scripts do projeto automaticamente a partir de main.py.
- Coletamos os dados do 'certifi' (bundle de CAs) para o SSL funcionar no exe.
- O FFmpeg NAO e embutido: o app baixa para ./bin na 1a execucao (Windows).
  Se preferir embutir, veja o comentario em 'binaries' abaixo.
"""

from PyInstaller.utils.hooks import collect_all

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

# --- EMBUTIR o ffmpeg.exe/ffprobe.exe (se existirem em ./bin) ---
# Assim o exe NAO baixa o FFmpeg na execucao: abre na hora e funciona offline.
import os
for _exe in ("ffmpeg.exe", "ffprobe.exe"):
    _p = os.path.join("bin", _exe)
    if os.path.isfile(_p):
        binaries.append((_p, "bin"))
    else:
        print(f"[spec] AVISO: {_p} nao encontrado; o exe baixara o FFmpeg na 1a execucao.")

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
