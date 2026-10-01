"""T040 — download do áudio, com tentativas.

O áudio é preservado depois do processamento (RF-09) por dois motivos que
compensam o espaço em disco: permite reprocessar quando a transcrição ou a
classificação melhorarem, e serve de prova contra falha silenciosa — se o
registro sumir, o original ainda está lá.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from ..log import obter, registrar
from .polling import ClienteTelegram

_log = obter("captura.download")


class FalhaNoDownload(Exception):
    """Erro nomeando a etapa, para o chat dizer onde parou."""


def extrair_audio(mensagem: dict) -> tuple[str, float | None] | None:
    """Devolve `(file_id, duração)` para voz ou áudio; `None` para o resto."""
    for chave in ("voice", "audio"):
        midia = mensagem.get(chave)
        if isinstance(midia, dict) and midia.get("file_id"):
            duracao = midia.get("duration")
            return midia["file_id"], float(duracao) if duracao else None
    return None


def baixar_audio(
    cliente: ClienteTelegram,
    file_id: str,
    destino: Path,
    tentativas: int = 3,
    timeout_s: int = 30,
    dormir=time.sleep,
) -> Path:
    ultimo: Exception | None = None

    for tentativa in range(max(1, tentativas)):
        try:
            caminho_remoto = cliente.caminho_do_arquivo(file_id)
            return cliente.baixar(caminho_remoto, destino, timeout_s)
        except Exception as erro:
            ultimo = erro
            registrar(
                _log,
                logging.WARNING,
                "falha no download do áudio",
                tentativa=tentativa + 1,
                de=tentativas,
                erro=str(erro),
            )
            if tentativa < tentativas - 1:
                dormir(2**tentativa)

    raise FalhaNoDownload(
        f"não foi possível baixar o áudio após {tentativas} tentativas: {ultimo}"
    )
