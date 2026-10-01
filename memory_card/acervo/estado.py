"""T024 — mudança de estado de um registro.

Escrita **restrita**: só `estado` e `estado_alterado_em` mudam. Assunto, tipo,
próximos passos, origem e sobretudo o texto bruto são copiados intactos.

Restringir a superfície de escrita é deliberado: o usuário edita conteúdo no
editor que já usa, e quanto menos o sistema puder alterar, menor o dano possível
de um defeito aqui.

O descarte consciente é o que impede o acervo de virar cemitério. Sem ele não há
como distinguir lixo de dívida, e a métrica de quatro ações por mês fica
ilegível: um acervo onde nada é descartado só cresce.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .escrita import gravar_registro
from .leitura import ler_registro
from .modelo import Estado, Registro


class ConflitoDeEdicao(Exception):
    """EC-04 do painel: o arquivo mudou em disco entre a leitura e a escrita.

    O conteúdo em disco é preservado e a marcação não é aplicada. Sobrescrever
    a edição do usuário para aplicar uma marcação seria trocar o dado dele pelo
    nosso metadado.
    """


class RegistroNaoEncontrado(Exception):
    """EC-07 do digest: link de um registro que o usuário apagou à mão."""


def alterar_estado(
    caminho: Path,
    novo: Estado,
    quando: datetime | None = None,
    esperado: str | None = None,
) -> Registro:
    """Aplica o novo estado e devolve o registro atualizado.

    `esperado` é o identificador que o chamador acredita estar naquele arquivo.
    O link do digest carrega o identificador, e o arquivo pode ter sido movido
    ou substituído desde o envio — conferir evita marcar o registro errado.

    Idempotente: marcar duas vezes o mesmo estado é operação válida e silenciosa,
    porque o usuário clica duas vezes e isso não pode virar erro.
    """
    if not caminho.exists():
        raise RegistroNaoEncontrado(f"registro não encontrado em {caminho}")

    atual = ler_registro(caminho)

    if esperado is not None and atual.id != esperado:
        raise ConflitoDeEdicao(
            f"o arquivo {caminho} contém o registro {atual.id}, não {esperado}"
        )

    if atual.estado is novo:
        return atual

    atualizado = atual.com_estado(novo, quando or datetime.now(timezone.utc))
    gravar_registro(caminho, atualizado)
    return atualizado


def marcar_executado(caminho: Path, esperado: str | None = None) -> Registro:
    return alterar_estado(caminho, Estado.EXECUTADO, esperado=esperado)


def marcar_descartado(caminho: Path, esperado: str | None = None) -> Registro:
    return alterar_estado(caminho, Estado.DESCARTADO, esperado=esperado)
