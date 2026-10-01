"""T050 — seleção dos registros do digest.

**Mais antigos primeiro, sem curadoria nenhuma.**

A regra é deliberadamente burra. Curadoria é um problema de produto tão difícil
quanto a classificação automática, e o mecanismo de devolução precisa existir
antes dela — é ele que gera o dado para medir a métrica de sucesso. Sem digest,
"quatro registros viram ação por mês" nasceria zero por construção, e não haveria
como distinguir fracasso do sistema de simples desuso.

Mais antigos primeiro faz o acervo **drenar de verdade**: nada apodrece no fundo.
O custo é conhecido e aceito — os primeiros envios trarão ideias velhas e o
descarte inicial será alto, o que é saudável, não fracasso.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..acervo.indice import EntradaIndice


@dataclass(frozen=True)
class Selecao:
    incluidos: tuple[EntradaIndice, ...]
    total_pendentes: int

    @property
    def vazia(self) -> bool:
        return not self.incluidos

    @property
    def restantes(self) -> int:
        return max(0, self.total_pendentes - len(self.incluidos))


def selecionar(entradas: list[EntradaIndice], limite: int) -> Selecao:
    pendentes = [e for e in entradas if e.estado == "pendente"]
    # Ordem crescente de captura: o mais antigo é o primeiro a voltar.
    pendentes.sort(key=lambda e: e.capturado_em)

    return Selecao(
        incluidos=tuple(pendentes[: max(0, limite)]),
        total_pendentes=len(pendentes),
    )
