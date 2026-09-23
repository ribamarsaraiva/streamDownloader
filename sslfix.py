"""
sslfix.py — Corrige verificacao de certificados SSL (foco no Windows).

Sintoma tipico:

    [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
    unable to get local issuer certificate

Causas comuns:
  1. O Python nao acha os certificados raiz (CA) do sistema.
  2. Antivirus/proxy CORPORATIVO que INSPECIONA TLS: ele reassina os
     certificados HTTPS com uma CA interna da empresa. Essa CA existe no
     armazenamento do Windows, mas NAO no bundle da Mozilla (certifi), entao
     a validacao falha.

Estrategia (sem desabilitar a verificacao):
  - Monta um bundle COMBINADO = certifi (Mozilla) + CAs do armazenamento do
    Windows (que inclui a CA interna instalada pela empresa/antivirus).
  - Aponta SSL_CERT_FILE e afins para esse bundle.
  - IMPORTANTE: o yt-dlp usa o PROPRIO certifi dele (from .dependencies import
    certifi) e chama certifi.where(). Por isso tambem sobrescrevemos
    certifi.where() para devolver o bundle combinado — assim o yt-dlp passa a
    confiar tambem na CA interna.

Use apply() o mais cedo possivel, ANTES de qualquer requisicao de rede.
"""

from __future__ import annotations

import os
import ssl
import sys
from pathlib import Path
from typing import List, Optional

# Diretorio base (funciona rodando .py ou empacotado com PyInstaller).
if getattr(sys, "frozen", False):
    _APP_DIR = Path(sys.executable).resolve().parent
else:
    _APP_DIR = Path(__file__).resolve().parent

# Onde gravamos o bundle combinado.
_COMBINED_CA = _APP_DIR / "bin" / "ca-bundle.pem"


def _certifi_path() -> Optional[str]:
    try:
        import certifi  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    try:
        path = certifi.where()
    except Exception:  # noqa: BLE001
        return None
    return path if path and os.path.isfile(path) else None


def _windows_store_ca_pems() -> List[str]:
    """
    Coleta as CAs confiaveis do armazenamento do Windows (ROOT e CA), em PEM.
    Retorna lista vazia fora do Windows ou se nada for encontrado.
    """
    pems: List[str] = []
    if not sys.platform.startswith("win") or not hasattr(ssl, "enum_certificates"):
        return pems

    for storename in ("ROOT", "CA"):
        try:
            certs = ssl.enum_certificates(storename)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            continue
        for cert_bytes, encoding, trust in certs:
            if encoding != "x509_asn":
                continue
            # trust True = confiavel para todos os usos; ou uso de server auth.
            if trust is True or (
                isinstance(trust, (set, frozenset, list, tuple))
                and getattr(ssl.Purpose.SERVER_AUTH, "oid", None) in trust
            ):
                try:
                    pem = ssl.DER_cert_to_PEM_cert(cert_bytes)
                    pems.append(pem)
                except Exception:  # noqa: BLE001
                    continue
    return pems


def _build_combined_bundle() -> Optional[str]:
    """
    Cria (ou atualiza) o bundle combinado certifi + CAs do Windows.
    Retorna o caminho do bundle, ou None se nao houver base certifi.
    """
    base = _certifi_path()
    if not base:
        return None

    try:
        base_data = Path(base).read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return None

    win_pems = _windows_store_ca_pems()
    # Se nao ha CAs extras do Windows, nao precisa combinar: usa o certifi puro.
    if not win_pems:
        return base

    try:
        _COMBINED_CA.parent.mkdir(parents=True, exist_ok=True)
        parts = [base_data.rstrip(), ""]
        parts.append("# ---- CAs do armazenamento do Windows (ROOT/CA) ----")
        parts.extend(p.strip() for p in win_pems)
        _COMBINED_CA.write_text("\n".join(parts) + "\n", encoding="utf-8")
        return str(_COMBINED_CA)
    except Exception:  # noqa: BLE001
        # Se nao conseguir gravar, cai para o certifi puro.
        return base


def _force_ytdlp_to_use(ca_path: str) -> None:
    """
    Faz o yt-dlp usar o bundle informado, sobrescrevendo certifi.where().
    O yt-dlp faz `from .dependencies import certifi` e chama certifi.where();
    ao trocar essa funcao, ele passa a confiar nas CAs do bundle combinado.
    """
    def _where(*_a, **_k):  # type: ignore[no-untyped-def]
        return ca_path

    # 1) O modulo certifi global (referenciado por outras libs).
    try:
        import certifi  # type: ignore

        certifi.where = _where  # type: ignore[assignment]
    except Exception:  # noqa: BLE001
        pass

    # 2) As referencias que o yt-dlp usa internamente, se ja importadas.
    for modname in ("yt_dlp.networking._helper", "yt_dlp.dependencies"):
        mod = sys.modules.get(modname)
        cert_ref = getattr(mod, "certifi", None) if mod else None
        if cert_ref is not None:
            try:
                cert_ref.where = _where  # type: ignore[assignment]
            except Exception:  # noqa: BLE001
                pass


def apply() -> bool:
    """
    Configura os certificados CA.

    Monta um bundle combinado (certifi + CAs do Windows) para cobrir tambem
    proxies/antivirus corporativos que inspecionam TLS, e faz urllib e yt-dlp
    usarem esse bundle.

    Retorna True se aplicou um bundle (certifi ou combinado), False caso
    contrario (sem certifi disponivel).
    """
    ca_path = _build_combined_bundle()
    if not ca_path:
        return False

    # 1) Variaveis de ambiente reconhecidas por OpenSSL/requests/urllib.
    os.environ["SSL_CERT_FILE"] = ca_path
    os.environ["SSL_CERT_DIR"] = os.path.dirname(ca_path)
    os.environ["REQUESTS_CA_BUNDLE"] = ca_path

    # 2) Contexto SSL padrao do Python.
    try:
        _orig = ssl.create_default_context

        def _default_context(*args, **kwargs):  # type: ignore[no-untyped-def]
            if "cafile" not in kwargs and "capath" not in kwargs and "cadata" not in kwargs:
                kwargs["cafile"] = ca_path
            return _orig(*args, **kwargs)

        if not getattr(ssl, "_sslfix_applied", False):
            ssl.create_default_context = _default_context  # type: ignore[assignment]
            ssl._sslfix_applied = True  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

    # 3) Forca o yt-dlp (e libs que usam certifi) a usar o bundle combinado.
    _force_ytdlp_to_use(ca_path)

    return True


def ca_file() -> Optional[str]:
    """Retorna o caminho do bundle de CAs em uso (combinado ou certifi)."""
    return os.environ.get("SSL_CERT_FILE") or _certifi_path()


def ytdlp_sees_certifi() -> bool:
    """
    Verifica se o yt-dlp consegue enxergar o certifi (usado para validar HTTPS).
    """
    try:
        from yt_dlp.networking._helper import certifi as _ytdlp_certifi  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from yt_dlp.dependencies import certifi as _ytdlp_certifi  # type: ignore
        except Exception:  # noqa: BLE001
            return False
    return _ytdlp_certifi is not None
