"""T029 — a fronteira única de classificação.

Este arquivo é o contrato. Todo o resto do sistema chama `classificar()` e
recebe uma `Classificacao`, sem saber qual provedor respondeu.

É essa fronteira que torna "qual provedor?" uma pergunta **não bloqueante**:
trocar de fornecedor é mudar configuração e, no máximo, um arquivo de
implementação. O critério de aceite do RF-04 é objetivo — substituir o adaptador
por uma versão simulada não pode exigir alteração em nenhum outro arquivo.

Nada aqui importa biblioteca de provedor nenhum. Se um `import` de fornecedor
aparecer neste arquivo, a fronteira vazou.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol


@dataclass(frozen=True)
class PedidoClassificacao:
    texto_bruto: str
    tipos_permitidos: tuple[str, ...]
    prompt: str
    modelo: str
    timeout_s: int
    # Reunião pede lista de encaminhamentos; nota curta, um só. A modalidade
    # é decidida fora daqui, pela duração do áudio.
    multiplos_passos: bool = False


@dataclass(frozen=True)
class Uso:
    """Alimenta o acompanhamento de custo. Sempre preenchido, mesmo em falha."""
    provedor: str = ""
    modelo: str = ""
    tokens_entrada: int = 0
    tokens_saida: int = 0


@dataclass(frozen=True)
class Classificacao:
    assunto: str
    tipo: str
    proximos_passos: tuple[str, ...]
    multiplos_temas: bool = False
    uso: Uso = field(default_factory=Uso)


class Adaptador(Protocol):
    """O contrato que todo provedor precisa satisfazer.

    Uma única operação. Quanto menor esta interface, mais barato é escrever o
    próximo adaptador — e é o custo do próximo adaptador que determina se a
    troca de provedor é real ou apenas teórica.
    """

    nome: str

    def classificar(self, pedido: PedidoClassificacao) -> Classificacao:
        ...


_REGISTRO: dict[str, Callable[..., Adaptador]] = {}


def registrar(nome: str, fabrica: Callable[..., Adaptador]) -> None:
    _REGISTRO[nome.strip().lower()] = fabrica


def adaptadores_disponiveis() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRO))


class ProvedorDesconhecido(Exception):
    """Falha na inicialização, não durante o processamento."""


def obter_adaptador(provedor: str, **opcoes) -> Adaptador:
    chave = (provedor or "").strip().lower()
    if chave not in _REGISTRO:
        disponiveis = ", ".join(adaptadores_disponiveis()) or "nenhum"
        raise ProvedorDesconhecido(
            f"LLM_PROVEDOR={provedor!r} não corresponde a nenhum adaptador. "
            f"Disponíveis: {disponiveis}."
        )
    return _REGISTRO[chave](**opcoes)
