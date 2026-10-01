"""T023 — arquivo markdown de volta para `Registro`.

O arquivo em disco é **sempre a fonte da verdade**. Se o usuário editar um
registro no editor dele, é a versão dele que vale; o índice é derivado e se
ajusta na reconstrução.

Por isso este módulo é tolerante: um arquivo com campo desconhecido, campo
faltando ou cabeçalho ligeiramente fora do formato ainda é lido, com os padrões
preenchendo as lacunas. Recusar-se a ler um arquivo que o usuário editou à mão
seria transformar uma edição legítima em perda de registro.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .modelo import Estado, Origem, Registro


class RegistroIlegivel(Exception):
    """EC-03 do painel: exibido como problemático, sem derrubar a listagem."""


def _para_datahora(valor: str) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        return None


def _para_booleano(valor: str) -> bool:
    return valor.strip().lower() in {"true", "1", "sim"}


def separar(conteudo: str) -> tuple[list[str], str]:
    """Divide em linhas de cabeçalho e corpo."""
    linhas = conteudo.splitlines()
    if not linhas or linhas[0].strip() != "---":
        raise RegistroIlegivel("arquivo sem cabeçalho de metadados")
    try:
        fim = next(i for i in range(1, len(linhas)) if linhas[i].strip() == "---")
    except StopIteration as erro:
        raise RegistroIlegivel("cabeçalho de metadados não foi fechado") from erro
    return linhas[1:fim], "\n".join(linhas[fim + 1 :])


def analisar_cabecalho(linhas: list[str]) -> dict[str, object]:
    campos: dict[str, object] = {}
    chave_lista: str | None = None

    for linha in linhas:
        if linha.startswith("  - ") and chave_lista:
            item = linha[4:].strip()
            try:
                item = json.loads(item)
            except json.JSONDecodeError:
                pass  # item gravado à mão pelo usuário, sem aspas
            campos.setdefault(chave_lista, []).append(item)  # type: ignore[union-attr]
            continue

        if ":" not in linha:
            continue

        chave, _, valor = linha.partition(":")
        chave, valor = chave.strip(), valor.strip()
        if not valor:
            campos[chave] = []
            chave_lista = chave
        else:
            campos[chave] = valor
            chave_lista = None
    return campos


def extrair_texto_bruto(corpo: str) -> str:
    marcador = "## Texto bruto"
    if marcador in corpo:
        return corpo.split(marcador, 1)[1].strip()
    # Arquivo sem a seção: devolve o corpo inteiro em vez de perder o conteúdo.
    return corpo.strip()


def ler_registro(caminho: Path) -> Registro:
    try:
        conteudo = caminho.read_text(encoding="utf-8")
    except OSError as erro:
        raise RegistroIlegivel(f"não foi possível ler {caminho}: {erro}") from erro

    linhas, corpo = separar(conteudo)
    campos = analisar_cabecalho(linhas)

    identificador = str(campos.get("id", "")).strip()
    if not identificador:
        raise RegistroIlegivel(f"{caminho} não tem identificador")

    capturado = _para_datahora(str(campos.get("capturado_em", "")))
    if capturado is None:
        raise RegistroIlegivel(f"{caminho} não tem data de captura válida")

    origem_bruta = str(campos.get("origem", "voz"))
    try:
        origem = Origem(origem_bruta)
    except ValueError:
        origem = Origem.VOZ

    estado_bruto = str(campos.get("estado", "pendente"))
    try:
        estado = Estado(estado_bruto)
    except ValueError:
        estado = Estado.PENDENTE

    duracao = campos.get("duracao_segundos")
    try:
        duracao_s = float(duracao) if duracao else None
    except (TypeError, ValueError):
        duracao_s = None

    passos = campos.get("proximos_passos") or []
    if isinstance(passos, str):
        passos = [passos]

    return Registro(
        id=identificador,
        capturado_em=capturado,
        origem=origem,
        texto_bruto=extrair_texto_bruto(corpo),
        assunto=str(campos.get("assunto", "")),
        tipo=str(campos.get("tipo", "")),
        proximos_passos=tuple(str(p) for p in passos),
        estado=estado,
        estado_alterado_em=_para_datahora(str(campos.get("estado_alterado_em", ""))),
        classificado=_para_booleano(str(campos.get("classificado", "false"))),
        motivo_nao_classificado=str(campos.get("motivo_nao_classificado", "")),
        audio_path=str(campos.get("audio_path", "")),
        duracao_segundos=duracao_s,
    )


def listar_registros(raiz: Path) -> list[tuple[Path, Registro]]:
    """Todos os registros do acervo, ordenados por data de captura.

    Arquivos ilegíveis são omitidos aqui e tratados pelo chamador — um arquivo
    corrompido não pode derrubar a listagem inteira.
    """
    encontrados: list[tuple[Path, Registro]] = []
    for caminho in sorted(raiz.rglob("*.md")):
        try:
            encontrados.append((caminho, ler_registro(caminho)))
        except RegistroIlegivel:
            continue
    encontrados.sort(key=lambda par: par[1].capturado_em)
    return encontrados
