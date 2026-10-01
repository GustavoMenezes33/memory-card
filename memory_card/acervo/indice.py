"""T025 — índice auxiliar.

**O índice pode morrer; os arquivos, não.** Ele é derivado, descartável e
reconstruível integralmente a partir do acervo — apagá-lo não perde nada e
reconstruí-lo produz exatamente o mesmo resultado.

Essa propriedade é o que permite ter desempenho de consulta sem abrir mão da
portabilidade: o acervo continua sendo um monte de arquivos markdown legíveis
sem nenhum software, e o índice é só um atalho.

Ele deliberadamente **não** guarda o texto bruto. Duplicar o conteúdo criaria
uma segunda cópia que pode divergir, e é exatamente o tipo de divergência que
destrói a confiança nas duas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .escrita import escrever_texto_atomico
from .leitura import listar_registros
from .modelo import Registro


@dataclass(frozen=True)
class EntradaIndice:
    id: str
    caminho: str
    capturado_em: str
    assunto: str
    tipo: str
    estado: str
    origem: str
    classificado: bool
    contem_terceiros: bool

    @classmethod
    def de(cls, caminho: Path, reg: Registro, raiz: Path) -> "EntradaIndice":
        try:
            relativo = caminho.relative_to(raiz).as_posix()
        except ValueError:
            relativo = caminho.as_posix()
        return cls(
            id=reg.id,
            caminho=relativo,
            capturado_em=reg.capturado_em.isoformat(timespec="seconds"),
            assunto=reg.assunto,
            tipo=reg.tipo,
            estado=reg.estado.value,
            origem=reg.origem.value,
            classificado=reg.classificado,
            contem_terceiros=reg.contem_terceiros,
        )


def construir(raiz: Path) -> list[EntradaIndice]:
    return [EntradaIndice.de(c, r, raiz) for c, r in listar_registros(raiz)]


def assinatura(raiz: Path) -> dict[str, object]:
    """Impressão digital barata do acervo em disco.

    Quantidade, tamanho somado e data de modificação mais recente mudam em
    qualquer escrita que o índice precise refletir: registro novo, registro
    apagado, estado alterado pelo painel, arquivo editado à mão no editor do
    usuário.

    Não é hash do conteúdo de propósito. Ler todos os markdown a cada visita ao
    painel custaria mais do que a reconstrução que a comparação quer evitar.
    """
    arquivos = 0
    tamanho = 0
    mtime = 0.0
    for caminho in raiz.rglob("*.md"):
        try:
            info = caminho.stat()
        except OSError:   # apagado entre o rglob e o stat
            continue
        arquivos += 1
        tamanho += info.st_size
        mtime = max(mtime, info.st_mtime)
    return {"arquivos": arquivos, "tamanho": tamanho, "mtime": round(mtime, 6)}


def salvar(
    destino: Path,
    entradas: list[EntradaIndice],
    assinatura_do_acervo: dict[str, object] | None = None,
) -> Path:
    corpo = json.dumps(
        {
            "versao": 1,
            "assinatura": assinatura_do_acervo or {},
            "entradas": [e.__dict__ for e in entradas],
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,   # determinístico: reconstruir gera bytes idênticos
    )
    return escrever_texto_atomico(destino, corpo + "\n")


def reconstruir(raiz: Path, destino: Path) -> list[EntradaIndice]:
    """EC-07. Apagar o índice e reconstruir produz o resultado anterior."""
    # A assinatura é colhida ANTES da leitura, e a ordem importa. Se um registro
    # for gravado enquanto esta função percorre o acervo, a assinatura guardada
    # já nasce velha e o próximo acesso reconstrói de novo. O erro barato é
    # reconstruir à toa; o caro seria o índice se declarar em dia sem o registro.
    antes = assinatura(raiz)
    entradas = construir(raiz)
    salvar(destino, entradas, antes)
    return entradas


def carregar(destino: Path, raiz: Path) -> list[EntradaIndice]:
    """Lê o índice; reconstrói sozinho se estiver ausente, corrompido ou velho.

    A verificação de idade é o que mantém a promessa de que **o arquivo em disco
    é sempre a fonte da verdade**. Sem ela o índice congela no estado em que foi
    criado — e como ele é a origem da listagem do painel e da seleção do digest,
    um índice congelado significa capturas que existem em disco e não aparecem
    em lugar nenhum.

    Índice velho ou corrompido não é erro para o usuário: é um arquivo derivado
    que o sistema regenera sem perguntar.
    """
    if not destino.exists():
        return reconstruir(raiz, destino)
    try:
        dados = json.loads(destino.read_text(encoding="utf-8"))
        if dados.get("assinatura") != assinatura(raiz):
            return reconstruir(raiz, destino)
        return [EntradaIndice(**e) for e in dados["entradas"]]
    except (json.JSONDecodeError, KeyError, TypeError, OSError):
        return reconstruir(raiz, destino)
