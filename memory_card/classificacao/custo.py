"""T034 — registro de custo por chamada.

O usuário **não definiu teto de custo**. Sem registro, a conta surpreende — e
surpreende exatamente quando o sistema está dando certo, porque o custo cresce
com o uso.

Reunião custa desproporcionalmente mais que nota de voz: transcrição longa como
entrada, e duas passagens em vez de uma. Por isso o registro guarda o perfil do
áudio, e não só o total: saber que o mês custou X é menos útil que saber que
três reuniões responderam por metade dele.

Os preços vêm de configuração, não de código. Tabela de preços embutida
envelhece em silêncio, e um custo estimado errado é pior que custo nenhum.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .fronteira import Uso


@dataclass(frozen=True)
class RegistroDeCusto:
    ts: str
    provedor: str
    modelo: str
    tokens_entrada: int
    tokens_saida: int
    custo_estimado: float | None
    perfil_audio: str
    passagens: int
    registro_id: str


def estimar(
    uso: Uso,
    preco_entrada_por_milhao: float | None,
    preco_saida_por_milhao: float | None,
) -> float | None:
    """`None` quando os preços não estão configurados.

    Devolver zero seria pior: um total de R$ 0,00 parece informação e é mentira.
    """
    if preco_entrada_por_milhao is None or preco_saida_por_milhao is None:
        return None
    entrada = uso.tokens_entrada / 1_000_000 * preco_entrada_por_milhao
    saida = uso.tokens_saida / 1_000_000 * preco_saida_por_milhao
    return round(entrada + saida, 6)


def anotar(
    arquivo: Path,
    uso: Uso,
    registro_id: str,
    perfil_audio: str = "curto",
    passagens: int = 1,
    preco_entrada_por_milhao: float | None = None,
    preco_saida_por_milhao: float | None = None,
) -> RegistroDeCusto:
    """Append-only. Uma linha JSON por chamada, para o painel somar por período."""
    entrada = RegistroDeCusto(
        ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        provedor=uso.provedor,
        modelo=uso.modelo,
        tokens_entrada=uso.tokens_entrada,
        tokens_saida=uso.tokens_saida,
        custo_estimado=estimar(uso, preco_entrada_por_milhao, preco_saida_por_milhao),
        perfil_audio=perfil_audio,
        passagens=passagens,
        registro_id=registro_id,
    )
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with arquivo.open("a", encoding="utf-8", newline="\n") as saida:
        saida.write(json.dumps(asdict(entrada), ensure_ascii=False) + "\n")
    return entrada


def somar_periodo(arquivo: Path, inicio: datetime, fim: datetime) -> dict:
    """Totais para o painel. Linha corrompida é ignorada, não derruba a soma."""
    totais = {
        "chamadas": 0,
        "tokens_entrada": 0,
        "tokens_saida": 0,
        "custo_estimado": 0.0,
        "custo_desconhecido": 0,
    }
    if not arquivo.exists():
        return totais

    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        try:
            dados = json.loads(linha)
            quando = datetime.fromisoformat(dados["ts"])
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if not (inicio <= quando <= fim):
            continue
        totais["chamadas"] += 1
        totais["tokens_entrada"] += int(dados.get("tokens_entrada", 0))
        totais["tokens_saida"] += int(dados.get("tokens_saida", 0))
        estimado = dados.get("custo_estimado")
        if estimado is None:
            totais["custo_desconhecido"] += 1
        else:
            totais["custo_estimado"] += float(estimado)
    totais["custo_estimado"] = round(totais["custo_estimado"], 4)
    return totais
