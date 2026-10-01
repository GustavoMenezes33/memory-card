"""T021 e T022 — onde o registro mora e como ele se chama.

O achado do enquadramento que este módulo materializa: **pasta é atrito quando
exige decisão humana no momento errado.** Dirigindo, ninguém escolhe categoria.
Derivada da data de captura — um dado que o sistema já tem — a pasta deixa de
custar qualquer coisa e a organização acontece sozinha.

O identificador é gerado aqui mas não depende daqui: ele vive nos metadados do
arquivo, então mover ou renomear não o altera (RF-07).
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

_INVALIDOS = re.compile(r"[^a-z0-9]+")


def gerar_id(quando: datetime | None = None) -> str:
    """`20260811-143052-a1b2c3`.

    O sufixo aleatório resolve o EC-01: duas capturas no mesmo segundo geram
    identificadores distintos sem precisar consultar o disco.
    """
    momento = (quando or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return f"{momento:%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"


def normalizar(assunto: str, limite: int) -> str:
    """Assunto → fragmento de nome de arquivo seguro em qualquer sistema.

    EC-04 e EC-08. O assunto original permanece **íntegro nos metadados**; o que
    é truncado e normalizado é apenas o nome do arquivo.
    """
    sem_acento = unicodedata.normalize("NFKD", assunto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    limpo = _INVALIDOS.sub("-", sem_acento.lower()).strip("-")
    if not limpo:
        return "sem-assunto"
    if len(limpo) <= limite:
        return limpo
    # Corta na fronteira de palavra mais próxima, para o nome continuar legível.
    cortado = limpo[:limite].rsplit("-", 1)[0]
    return cortado or limpo[:limite]


def pasta_do_periodo(raiz: Path, quando: datetime, granularidade: str) -> Path:
    """RF-04. Derivada da data, sem nenhuma intervenção do usuário."""
    momento = quando.astimezone(timezone.utc)
    if granularidade == "semanal":
        ano, semana, _ = momento.isocalendar()
        return raiz / f"{ano}-S{semana:02d}"
    return raiz / f"{momento:%Y-%m}"


def caminho_do_registro(
    raiz: Path,
    identificador: str,
    assunto: str,
    quando: datetime,
    granularidade: str = "mensal",
    limite_nome: int = 80,
) -> Path:
    """Caminho completo, já resolvendo colisão de nome.

    `limite_nome` vale para o **nome inteiro**, não só para o fragmento derivado
    do assunto. O identificador ocupa 23 caracteres fixos, então limitar apenas
    o assunto deixaria o nome final estourar o limite configurado — e o Windows
    tem teto de 260 caracteres para o caminho completo, que uma pasta de acervo
    aninhada consome rápido.

    A colisão é improvável (o identificador carrega sufixo aleatório) mas
    tratada mesmo assim: sobrescrever um registro do usuário é inaceitável, e
    o custo de verificar é um `exists()`.
    """
    pasta = pasta_do_periodo(raiz, quando, granularidade)

    # Orçamento do assunto: o que sobra depois do identificador, do hífen que
    # os separa e de uma folga para o sufixo de colisão.
    orcamento = max(8, limite_nome - len(identificador) - 4)
    base = f"{identificador}-{normalizar(assunto, orcamento)}"

    candidato = pasta / f"{base}.md"
    sufixo = 2
    while candidato.exists():
        candidato = pasta / f"{base}-{sufixo}.md"
        sufixo += 1
    return candidato
