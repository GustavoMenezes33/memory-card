"""T036 — máquina de etapas com retomada.

A garantia que este módulo entrega: **um reinício no meio do processamento não
duplica registro nem repete etapa concluída.**

O mecanismo é simples e é o que torna exatamente-uma-vez implementável sem
transação: cada etapa é persistida **assim que termina**. Ao retomar, o item
carrega a última etapa concluída e o trabalho continua da seguinte. Uma queda
entre a transcrição e a classificação custa a classificação, não a transcrição
de novo — que é justamente a etapa cara.

A ordem de persistência importa mais do que parece: persistir **depois** de
executar significa que, na pior das hipóteses, uma etapa roda duas vezes.
Persistir **antes** significaria pular uma etapa que nunca rodou — trocar
duplicata por perda, e perda é inaceitável.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .modelo import Etapa, ItemFila, salvar

# Uma etapa recebe o item e devolve os campos que ela produziu.
Executor = Callable[[ItemFila], dict]


@dataclass
class Maquina:
    pasta: Path
    executores: dict[Etapa, Executor]

    def executar_ate_o_fim(self, item: ItemFila, max_etapas: int = 10) -> ItemFila:
        """Avança o item até arquivar ou falhar.

        `max_etapas` é uma trava de segurança contra laço infinito: a esteira
        tem cinco etapas, então o limite nunca é atingido em operação normal.
        Se for, há defeito na máquina e travar é melhor que girar para sempre.
        """
        atual = item
        for _ in range(max_etapas):
            if atual.concluido:
                break

            executor = self.executores.get(atual.etapa)
            if executor is None:
                atual = atual.falhar(f"sem executor para a etapa {atual.etapa.value}")
                salvar(self.pasta, atual)
                break

            try:
                produzido = executor(atual)
            except Exception as erro:
                atual = atual.falhar(f"{type(erro).__name__}: {erro}")
                salvar(self.pasta, atual)
                break

            # Persistir só depois de a etapa ter concluído de verdade.
            atual = atual.avancar(**produzido)
            salvar(self.pasta, atual)
        return atual


def retomar(item: ItemFila) -> Etapa:
    """A etapa por onde continuar. Concluído continua concluído."""
    return item.etapa
