"""Log estruturado central.

Duas regras não negociáveis, ambas vindas dos requisitos de segurança e
privacidade:

1. Segredo nunca é registrado. Token, chave de API e senha de e-mail são
   mascarados mesmo quando alguém os passa por engano.
2. Conteúdo capturado nunca vai para log de nível informativo. O acervo é
   pessoal, e log costuma ser o lugar que ninguém lembra de proteger.

O que É registrado, por exigência de observabilidade: identificador da
mensagem, etapa, duração, modelo, tokens, custo estimado e desfecho.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

_PADROES_SEGREDO = (
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),   # token de bot
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),          # chave de API
    re.compile(r"\b[A-Za-z0-9_-]{32,}\b"),             # segredo genérico longo
)

_CAMPOS_SENSIVEIS = {
    "token", "api_key", "senha", "password", "secret",
    "texto_bruto", "transcricao", "conteudo",
}


def mascarar(valor: str) -> str:
    """Substitui o que parece segredo. Melhor mascarar demais que de menos."""
    for padrao in _PADROES_SEGREDO:
        valor = padrao.sub("***", valor)
    return valor


class FormatadorJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "nivel": record.levelname,
            "origem": record.name,
            "msg": mascarar(record.getMessage()),
        }

        extra = getattr(record, "dados", None)
        if isinstance(extra, dict):
            for chave, valor in extra.items():
                if chave.lower() in _CAMPOS_SENSIVEIS:
                    payload[chave] = "***"
                elif isinstance(valor, str):
                    payload[chave] = mascarar(valor)
                else:
                    payload[chave] = valor

        if record.exc_info:
            payload["excecao"] = mascarar(self.formatException(record.exc_info))

        return json.dumps(payload, ensure_ascii=False)


def configurar(nivel: str = "INFO") -> None:
    raiz = logging.getLogger()
    raiz.setLevel(getattr(logging, nivel.upper(), logging.INFO))
    raiz.handlers.clear()

    saida = logging.StreamHandler(sys.stdout)
    saida.setFormatter(FormatadorJSON())
    raiz.addHandler(saida)


def obter(nome: str) -> logging.Logger:
    return logging.getLogger(nome)


def registrar(logger: logging.Logger, nivel: int, msg: str, **dados: Any) -> None:
    """Log com campos estruturados.

    Uso: registrar(log, logging.INFO, "transcricao concluida",
                   message_id=42, duracao_s=31.4, modelo="small")
    """
    logger.log(nivel, msg, extra={"dados": dados})
