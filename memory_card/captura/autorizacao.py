"""T039 — autorização por identificador único.

Sem esta checagem, qualquer pessoa que descubra o nome do bot injeta conteúdo
no acervo, e o usuário passa a ter registros de origem desconhecida misturados
aos dele. É correção trivial no começo e constrangedora depois.

**O descarte é silencioso, e isso é deliberado.** Responder a um remetente não
autorizado confirmaria a existência do bot a quem não deveria saber. A tentativa
é registrada em log, onde o dono vê; o desconhecido não recebe nada.
"""

from __future__ import annotations

import logging

from ..log import obter, registrar

_log = obter("captura.autorizacao")


def remetente_de(mensagem: dict) -> int | None:
    origem = mensagem.get("from") or {}
    identificador = origem.get("id")
    return int(identificador) if identificador is not None else None


def autorizado(mensagem: dict, usuario_autorizado: int) -> bool:
    """Nunca há modo permissivo: identificador diferente é sempre recusa."""
    remetente = remetente_de(mensagem)
    if remetente == usuario_autorizado:
        return True

    registrar(
        _log,
        logging.WARNING,
        "mensagem de remetente não autorizado descartada",
        remetente=remetente,
        message_id=mensagem.get("message_id"),
    )
    return False
