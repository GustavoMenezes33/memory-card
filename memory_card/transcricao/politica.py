"""T027 — política por duração: nota curta ou áudio longo.

Decisão D-02 do roadmap: **uma esteira só, com política por duração**, em vez de
dois caminhos separados. As quatro etapas são idênticas nos dois casos; o que
muda são limites e a forma de classificar. Duplicar a esteira duplicaria também
o tratamento de erro, que é a parte mais delicada de manter em duplicata.

A premissa está registrada com um sintoma observável: se condicionais por
duração aparecerem em **mais de três pontos** do código, a diferença é
estrutural e vale separar os caminhos. Hoje são dois — aqui e na classificação.

⚠️ Confidência 🔴: o limite padrão de 180 segundos é hipótese, não medição.
Ele separa uma nota de voz ao volante (30 a 60 s) de uma reunião (dezenas de
minutos), mas o ponto de corte real só se conhece observando o uso.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Perfil(str, Enum):
    CURTO = "curto"
    LONGO = "longo"


@dataclass(frozen=True)
class Politica:
    perfil: Perfil
    timeout_s: int
    avisar_processamento_estendido: bool

    @property
    def e_longo(self) -> bool:
        return self.perfil is Perfil.LONGO


def decidir(
    duracao_segundos: float | None,
    limite_longo_s: int,
    timeout_curto_s: int,
    timeout_longo_s: int,
) -> Politica:
    """Duração desconhecida é tratada como curta.

    Escolha deliberada: aplicar o tratamento de reunião a um áudio de duração
    desconhecida custaria classificação em duas passagens — e o dobro de API —
    para uma nota de trinta segundos. O erro barato é o oposto: se um áudio
    longo escapar como curto, ele estoura o tempo limite e falha visivelmente,
    o que é diagnosticável.
    """
    if duracao_segundos is not None and duracao_segundos > limite_longo_s:
        return Politica(Perfil.LONGO, timeout_longo_s, avisar_processamento_estendido=True)
    return Politica(Perfil.CURTO, timeout_curto_s, avisar_processamento_estendido=False)
