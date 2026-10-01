"""T042 — captura por texto digitado.

Fluxo alternativo: quando não dá para falar, o texto entra como **transcrição
pronta** e pula a etapa de transcrição. Não é o problema que motivou o projeto,
mas é um caminho de custo quase zero que aproveita toda a esteira já existente.
"""

from __future__ import annotations

from ..fila.modelo import Etapa, ItemFila


def extrair_texto(mensagem: dict) -> str | None:
    texto = mensagem.get("text")
    if isinstance(texto, str) and texto.strip():
        return texto.strip()
    return None


def e_comando(texto: str | None) -> bool:
    """Comando do Telegram (`/start`, `/help`) não é captura.

    Todo usuário manda `/start`: é o botão que abre a conversa com o bot, não
    uma escolha. Sem esta porta o comando entra na esteira como texto comum,
    gasta uma chamada de API e deixa no acervo um registro que o usuário nunca
    quis — e que ainda apareceria no digest, competindo com insight de verdade.
    """
    return bool(texto) and texto.strip().startswith("/")


def item_de_texto(
    identificador: str, mensagem: dict, texto: str
) -> ItemFila:
    """Nasce já em `TRANSCRITO`: não há áudio para baixar nem transcrever.

    Reaproveitar a máquina de etapas em vez de criar um caminho paralelo é o que
    mantém uma esteira só — a decisão D-02 do roadmap valendo também aqui.
    """
    return ItemFila(
        id=identificador,
        telegram_message_id=int(mensagem.get("message_id", 0)),
        telegram_chat_id=int((mensagem.get("chat") or {}).get("id", 0)),
        tipo_origem="texto",
        etapa=Etapa.TRANSCRITO,
        texto_bruto=texto,
    )
