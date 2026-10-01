"""T049 — filtros e busca textual.

Busca simples de propósito. Busca semântica é não-objetivo declarado, e há um
motivo mais forte que o escopo: **busca só encontra o que o usuário lembra que
existe.** O insight esquecido não vai ser digitado numa caixa de busca — quem
resolve isso é o digest, que traz o registro de volta sem depender da memória.

A busca aqui serve ao caso em que ele *lembra* e quer reencontrar. Confundir os
dois papéis levaria a investir na ferramenta errada.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from ..acervo.indice import EntradaIndice
from ..acervo.leitura import RegistroIlegivel, ler_registro


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sem_acento if not unicodedata.combining(c))


def filtrar(
    entradas: list[EntradaIndice],
    estado: str | None = None,
    tipo: str | None = None,
    origem: str | None = None,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    incluir_descartados: bool = False,
) -> list[EntradaIndice]:
    resultado = list(entradas)

    if not incluir_descartados and estado != "descartado":
        resultado = [e for e in resultado if e.estado != "descartado"]
    if estado:
        resultado = [e for e in resultado if e.estado == estado]
    if tipo:
        resultado = [e for e in resultado if e.tipo == tipo]
    if origem:
        resultado = [e for e in resultado if e.origem == origem]

    if inicio or fim:
        def no_intervalo(entrada: EntradaIndice) -> bool:
            try:
                quando = datetime.fromisoformat(entrada.capturado_em)
            except ValueError:
                return False
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=timezone.utc)
            if inicio and quando < inicio:
                return False
            if fim and quando > fim:
                return False
            return True

        resultado = [e for e in resultado if no_intervalo(e)]
    return resultado


def buscar(
    entradas: list[EntradaIndice], termo: str, raiz: Path
) -> list[EntradaIndice]:
    """Procura no assunto e, se não achar, no texto bruto do arquivo.

    O assunto vem do índice e é barato; o texto bruto exige abrir o arquivo. A
    ordem existe para que a busca comum não pague o custo da busca profunda.
    """
    alvo = _normalizar(termo.strip())
    if not alvo:
        return list(entradas)

    por_assunto = [e for e in entradas if alvo in _normalizar(e.assunto)]
    ja_encontrados = {e.id for e in por_assunto}

    por_texto: list[EntradaIndice] = []
    for entrada in entradas:
        if entrada.id in ja_encontrados:
            continue
        try:
            registro = ler_registro(raiz / entrada.caminho)
        except (RegistroIlegivel, OSError):
            continue
        if alvo in _normalizar(registro.texto_bruto):
            por_texto.append(entrada)

    return por_assunto + por_texto


def tipos_presentes(entradas: list[EntradaIndice]) -> list[str]:
    return sorted({e.tipo for e in entradas if e.tipo})
