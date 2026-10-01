"""T048 — marcação em duas etapas.

**O requisito de integridade mais importante do sistema.**

Clientes de e-mail, antivírus e filtros de segurança **pré-carregam endereços**
contidos em mensagens, para checar reputação e gerar pré-visualização. Se o link
do digest alterasse o estado ao ser carregado, essas ferramentas marcariam
registros sozinhas, e o usuário encontraria itens "executados" que nunca tocou.

O dano não seria o registro errado: seria a perda de confiança. Um acervo que se
altera sozinho deixa de ser confiável inteiro, inclusive na parte correta — e o
produto existe justamente para o usuário confiar que o insight está guardado.

Por isso: **leitura nunca altera nada; só o envio explícito aplica.**
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from ..acervo.estado import ConflitoDeEdicao, alterar_estado
from ..acervo.modelo import Estado
from .registro import localizar

ACOES = {
    "executado": Estado.EXECUTADO,
    "descartado": Estado.DESCARTADO,
}


class AcaoDesconhecida(Exception):
    pass


@dataclass(frozen=True)
class Situacao:
    """O que a página de confirmação precisa mostrar."""
    encontrado: bool
    ja_no_estado: bool = False
    conflito: bool = False
    identificador: str = ""
    acao: str = ""
    assunto: str = ""
    estado_atual: str = ""
    proximos_passos: tuple[str, ...] = ()
    mensagem: str = ""


def validar_acao(acao: str) -> Estado:
    if acao not in ACOES:
        raise AcaoDesconhecida(
            f"ação {acao!r} desconhecida. Válidas: {', '.join(sorted(ACOES))}."
        )
    return ACOES[acao]


def url_de_marcacao(base: str, identificador: str, acao: str) -> str:
    """O endereço que vai gravado dentro do e-mail.

    Ele fica na caixa do usuário indefinidamente, então tem estabilidade de
    contrato público: mudar este formato quebra digests já enviados.
    """
    return f"{base.rstrip('/')}/registro/{quote(identificador)}/marcar/{acao}"


def preparar(identificador: str, acao: str, raiz: Path, indice: Path) -> Situacao:
    """GET. **Não altera nada** — apenas descreve o que aconteceria."""
    validar_acao(acao)
    encontrado = localizar(identificador, raiz, indice)

    if encontrado is None:
        return Situacao(
            encontrado=False,
            identificador=identificador,
            acao=acao,
            mensagem=(
                "Este registro não existe mais. Ele pode ter sido apagado "
                "manualmente depois que o digest foi enviado."
            ),
        )

    registro = encontrado.registro
    return Situacao(
        encontrado=True,
        ja_no_estado=registro.estado.value == acao,
        identificador=identificador,
        acao=acao,
        assunto=registro.assunto or "(sem assunto)",
        estado_atual=registro.estado.value,
        proximos_passos=registro.proximos_passos,
        mensagem=(
            f"Este registro já está marcado como {acao}."
            if registro.estado.value == acao
            else ""
        ),
    )


def aplicar(identificador: str, acao: str, raiz: Path, indice: Path) -> Situacao:
    """POST. Idempotente: confirmar duas vezes produz o mesmo estado final.

    O usuário clica duas vezes quando a resposta demora, e isso não pode virar
    erro.
    """
    novo = validar_acao(acao)
    encontrado = localizar(identificador, raiz, indice)

    if encontrado is None:
        return Situacao(
            encontrado=False,
            identificador=identificador,
            acao=acao,
            mensagem="Este registro não existe mais; nada foi alterado.",
        )

    try:
        registro = alterar_estado(
            encontrado.caminho, novo, esperado=identificador
        )
    except ConflitoDeEdicao:
        return Situacao(
            encontrado=True,
            conflito=True,
            identificador=identificador,
            acao=acao,
            assunto=encontrado.registro.assunto,
            estado_atual=encontrado.registro.estado.value,
            mensagem=(
                "O arquivo mudou em disco desde a leitura. A marcação não foi "
                "aplicada e o conteúdo em disco foi preservado."
            ),
        )

    return Situacao(
        encontrado=True,
        identificador=identificador,
        acao=acao,
        assunto=registro.assunto or "(sem assunto)",
        estado_atual=registro.estado.value,
        proximos_passos=registro.proximos_passos,
        mensagem=f"Registro marcado como {registro.estado.value}.",
    )
