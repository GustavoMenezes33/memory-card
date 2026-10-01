"""T046 — as contagens do período.

O painel responde a **uma** pergunta: o sistema está gerando ação ou apenas
acumulando conteúdo? Tudo aqui existe para tornar aferível a métrica de quatro
registros virando ação por mês.

Sem armazenamento próprio: tudo é derivado do acervo. Duas fontes divergiriam e
destruiriam a confiança nas duas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..acervo.indice import EntradaIndice


@dataclass(frozen=True)
class VisaoPeriodo:
    periodo_inicio: datetime
    periodo_fim: datetime
    total_capturados: int = 0
    total_arquivados: int = 0
    total_executados: int = 0
    total_descartados: int = 0
    total_pendentes: int = 0
    total_com_falha: int = 0
    total_reunioes: int = 0

    @property
    def meta_mensal_atingida(self) -> bool:
        """A meta declarada pelo usuário: 4 registros virando ação por mês."""
        return self.total_executados >= 4


def limites_do_periodo(
    referencia: datetime | None = None, modo: str = "mes-corrente"
) -> tuple[datetime, datetime]:
    agora = (referencia or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if modo == "ultimos-30-dias":
        return agora - timedelta(days=30), agora
    inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return inicio, agora


def _dentro(entrada: EntradaIndice, inicio: datetime, fim: datetime) -> bool:
    try:
        quando = datetime.fromisoformat(entrada.capturado_em)
    except ValueError:
        return False
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=timezone.utc)
    return inicio <= quando <= fim


def calcular(
    entradas: list[EntradaIndice], inicio: datetime, fim: datetime
) -> VisaoPeriodo:
    do_periodo = [e for e in entradas if _dentro(e, inicio, fim)]

    return VisaoPeriodo(
        periodo_inicio=inicio,
        periodo_fim=fim,
        total_capturados=len(do_periodo),
        # Arquivado é todo registro que chegou ao acervo — o que inclui os que
        # falharam na classificação. A distinção importa: um registro sem
        # estrutura ainda é um insight preservado.
        total_arquivados=len(do_periodo),
        total_executados=sum(1 for e in do_periodo if e.estado == "executado"),
        total_descartados=sum(1 for e in do_periodo if e.estado == "descartado"),
        total_pendentes=sum(1 for e in do_periodo if e.estado == "pendente"),
        total_com_falha=sum(1 for e in do_periodo if not e.classificado),
        total_reunioes=sum(1 for e in do_periodo if e.origem == "reuniao"),
    )
