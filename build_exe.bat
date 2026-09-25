@echo off
REM ============================================================================
REM  build_exe.bat - Gera StreamDownloader.exe TOTALMENTE AUTONOMO
REM  (sem download de FFmpeg, PySide6, yt-dlp etc. na execucao)
REM
REM  Requisitos:
REM    - Python 3.9+ no PATH
REM    - Internet so nesta etapa de BUILD (para baixar FFmpeg se faltar)
REM ============================================================================
setlocal
cd /d "%~dp0"

echo.
echo === StreamDownloader - build de executavel autonomo ===
echo.

REM 1) Dependencias de build
echo [1/4] Instalando dependencias de build (PySide6, yt-dlp, certifi, pyinstaller)...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :pip_fail

REM 2) Garantir FFmpeg em ./bin (baixa so se faltar - so no BUILD)
echo.
echo [2/4] Garantindo FFmpeg em .\bin\ ...
if exist "bin\ffmpeg.exe" goto :ffmpeg_ok

echo      FFmpeg ausente - baixando essentials (uma unica vez no build)...
python -c "import deps; r=deps.ensure_ffmpeg(); print('ffmpeg =', r); raise SystemExit(0 if r else 1)"
if errorlevel 1 goto :ffmpeg_fail
goto :ffmpeg_check_probe

:ffmpeg_ok
echo      OK: bin\ffmpeg.exe ja existe.

:ffmpeg_check_probe
if exist "bin\ffprobe.exe" goto :clean
echo AVISO: bin\ffprobe.exe nao encontrado. O app funciona, mas alguns
echo        pos-processamentos do yt-dlp podem falhar. Prefira o pack
echo        essentials completo (ffmpeg + ffprobe).

:clean
REM 3) Limpar builds anteriores
echo.
echo [3/4] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 4) Gerar o .exe com FFmpeg embutido
echo.
echo [4/4] Gerando StreamDownloader.exe (isso pode demorar 1-3 min)...
python -m PyInstaller StreamDownloader.spec
if errorlevel 1 goto :pyi_fail

echo.
echo ============================================================================
echo  Pronto!
echo  Executavel: dist\StreamDownloader.exe
echo.
echo  Ele e portatil e autonomo: nao precisa de Python, nem baixa FFmpeg
echo  nem pacotes na primeira execucao. Basta copiar o .exe e rodar.
echo ============================================================================
echo.
endlocal
exit /b 0

:pip_fail
echo ERRO: falha ao instalar pacotes. Verifique o Python/pip.
endlocal
exit /b 1

:ffmpeg_fail
echo ERRO: nao foi possivel obter o FFmpeg.
endlocal
exit /b 1

:pyi_fail
echo ERRO: PyInstaller falhou.
endlocal
exit /b 1
