"""T033 — erros distintos e política de novas tentativas.

A hierarquia inteira serve a uma regra do produto: **falha de classificação
nunca impede o arquivamento.** Perder o insight é inaceitável; perder a
estrutura é recuperável, porque o texto bruto permanece íntegro e permite
reclassificar depois.

Por isso os erros são separados por *causa*, e não por gravidade: cota esgotada
é problema financeiro, recusa é decisão do provedor, indisponibilidade é
transitória. Só a última merece nova tentativa, e confundi-las faz o sistema
insistir onde não adianta ou desistir onde bastava esperar.
"""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar


class ErroDeClassificacao(Exception):
    """Base. Nenhum destes impede o arquivamento do registro."""

    motivo = "erro"


class Indisponivel(ErroDeClassificacao):
    """EC-01. Transitório: vale tentar de novo."""
    motivo = "provedor indisponível"


class TempoExcedido(Indisponivel):
    """EC-09. Tratado como transitório."""
    motivo = "tempo excedido"


class RespostaInvalida(ErroDeClassificacao):
    """EC-02 e EC-03. Uma nova tentativa, depois desiste."""
    motivo = "resposta em formato inválido"


class CotaEsgotada(ErroDeClassificacao):
    """EC-06. Nome próprio para a causa ser evidente: é financeira, não técnica.

    Tentar de novo só queima tempo — o saldo não volta sozinho.
    """
    motivo = "cota ou saldo esgotado"


class ConteudoRecusado(ErroDeClassificacao):
    """EC-10. O registro do usuário nunca é descartado por decisão de terceiro."""
    motivo = "conteúdo recusado pelo provedor"


class CredencialInvalida(ErroDeClassificacao):
    """Falha na inicialização, não durante o processamento."""
    motivo = "credencial inválida"


T = TypeVar("T")

# Só o que é transitório entra na política de repetição.
_TRANSITORIOS = (Indisponivel,)


def com_novas_tentativas(
    operacao: Callable[[], T],
    tentativas: int,
    espera_inicial_s: float = 1.0,
    dormir: Callable[[float], None] = time.sleep,
) -> T:
    """Espera crescente com variação aleatória.

    A variação evita que várias falhas simultâneas voltem no mesmo instante.
    Com uma máquina e um usuário isso é quase irrelevante hoje — mas é uma linha
    de código, e a alternativa é descobrir o problema quando já houver volume.
    """
    ultimo: Exception | None = None
    for tentativa in range(max(1, tentativas)):
        try:
            return operacao()
        except _TRANSITORIOS as erro:
            ultimo = erro
            if tentativa == tentativas - 1:
                break
            espera = espera_inicial_s * (2**tentativa)
            dormir(espera + random.uniform(0, espera * 0.25))
    raise ultimo if ultimo else Indisponivel("falha sem causa registrada")
