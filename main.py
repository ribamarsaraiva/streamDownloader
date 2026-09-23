"""
main.py — Ponto de entrada do Stream Downloader.

1. Verifica e instala dependencias (PySide6, yt-dlp, FFmpeg).
2. Se PySide6 foi instalado agora, reinicia o processo para carrega-lo.
3. Sobe a interface desktop.

Uso:
    python main.py
"""

from __future__ import annotations

import os
import sys

import deps


def _bootstrap() -> str:
    """Garante dependencias. Retorna o caminho do ffmpeg (ou string vazia)."""
    result = deps.ensure_all(log=print)

    if not result["pip_ok"]:
        print(
            "\nNao foi possivel instalar todas as dependencias Python.\n"
            "Verifique sua conexao e se o pip esta funcionando, e tente novamente."
        )
        sys.exit(1)

    ffmpeg = result["ffmpeg"] or ""
    if not ffmpeg:
        print(
            "\nAVISO: FFmpeg nao esta disponivel. Downloads que exigem juntar\n"
            "audio+video ou converter para MP3 podem falhar."
        )
    return ffmpeg


def main() -> None:
    ffmpeg = _bootstrap()

    # Corrige verificacao de certificados SSL (usa o bundle do certifi).
    # Precisa rodar DEPOIS do bootstrap (que instala o certifi) e ANTES de
    # qualquer requisicao de rede do yt-dlp.
    try:
        import sslfix

        if sslfix.apply():
            print(f"SSL: usando bundle de certificados: {sslfix.ca_file()}")
        else:
            print("SSL: certifi indisponivel; usando certificados do sistema.")

        # O yt-dlp usa o PROPRIO certifi dele (from .dependencies import certifi).
        # Se ele nao enxergar o certifi, e a causa provavel do
        # CERTIFICATE_VERIFY_FAILED — avisamos de forma acionavel.
        if not sslfix.ytdlp_sees_certifi():
            print(
                "SSL: AVISO — o yt-dlp NAO esta enxergando o 'certifi'. Isso "
                "costuma causar 'CERTIFICATE_VERIFY_FAILED'.\n"
                "     Rode: pip install --upgrade certifi\n"
                "     (ou, atras de proxy corporativo, defina SD_NO_CHECK_CERT=1 "
                "como ultimo recurso)."
            )
    except Exception as exc:  # noqa: BLE001
        print(f"SSL: nao foi possivel aplicar o fix de certificados ({exc}).")

    # Reinicio unico: se o PySide6 acabou de ser instalado, o import pode falhar
    # neste processo. Reiniciamos UMA vez com uma flag de ambiente — mas apenas
    # se a falha for realmente por causa de dependencia recem-instalada
    # (PySide6/shiboken6), e nao por um erro de codigo no proprio ui.py.
    try:
        import ui  # noqa: F401  (import tardio, apos garantir deps)
    except ImportError as exc:
        dep_missing = (exc.name or "").split(".")[0] in {"PySide6", "shiboken6"}
        # No modo empacotado (.exe) nao ha reinstalacao nem reinicio: as deps
        # ja estao embutidas, entao um ImportError aqui e um erro real.
        frozen = getattr(sys, "frozen", False)
        if not frozen and dep_missing and os.environ.get("SD_RESTARTED") != "1":
            print("Reiniciando para carregar dependencias recem-instaladas...")
            os.environ["SD_RESTARTED"] = "1"
            os.execv(sys.executable, [sys.executable, *sys.argv])
        raise

    sys.exit(ui.run(ffmpeg_path=ffmpeg or None))


if __name__ == "__main__":
    main()
