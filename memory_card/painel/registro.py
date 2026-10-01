"""T047 — o registro individual.

Localiza um registro pelo identificador, não pelo caminho. É o que permite ao
usuário mover e renomear arquivos livremente sem quebrar os links já enviados
em digests antigos.

A busca varre o índice primeiro e o disco só como último recurso: o índice pode
estar defasado se o usuário mexeu nos arquivos, e nesse caso os arquivos vencem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..acervo.indice import EntradaIndice, carregar
from ..acervo.leitura import RegistroIlegivel, ler_registro, listar_registros
from ..acervo.modelo import Registro


@dataclass(frozen=True)
class RegistroLocalizado:
    caminho: Path
    registro: Registro


def localizar(
    identificador: str, raiz: Path, arquivo_indice: Path
) -> RegistroLocalizado | None:
    """`None` quando o registro não existe mais — apagado à mão, por exemplo."""
    for entrada in carregar(arquivo_indice, raiz):
        if entrada.id != identificador:
            continue
        caminho = raiz / entrada.caminho
        if caminho.exists():
            try:
                return RegistroLocalizado(caminho, ler_registro(caminho))
            except RegistroIlegivel:
                break
        break   # índice defasado: cai para a varredura em disco

    for caminho, registro in listar_registros(raiz):
        if registro.id == identificador:
            return RegistroLocalizado(caminho, registro)
    return None


def entradas_ordenadas(raiz: Path, arquivo_indice: Path) -> list[EntradaIndice]:
    """Mais recentes primeiro — a ordem que o painel usa para listar."""
    entradas = carregar(arquivo_indice, raiz)
    return sorted(entradas, key=lambda e: e.capturado_em, reverse=True)
