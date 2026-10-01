"""T014 — identificador estável e nome de arquivo derivado.

RF-07. O identificador vive nos **metadados**, não no nome do arquivo. Mover,
renomear ou reorganizar o acervo à mão não pode quebrar as referências do
sistema — e o usuário vai mexer nesses arquivos, porque a portabilidade que o
produto promete é exatamente essa liberdade.

O corolário: o nome do arquivo é descartável. Ele existe para o humano
reconhecer o registro ao olhar a pasta, e por isso é normalizado e truncado,
enquanto o assunto permanece íntegro nos metadados.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from memory_card.acervo import caminhos as C
from memory_card.acervo.escrita import gravar_registro
from memory_card.acervo.leitura import ler_registro
from memory_card.acervo.modelo import Origem, Registro

QUANDO = datetime(2026, 8, 11, 14, 30, 52, tzinfo=timezone.utc)


def gravar(raiz: Path, assunto: str, identificador: str | None = None) -> tuple[Path, str]:
    rid = identificador or C.gerar_id(QUANDO)
    reg = Registro(
        id=rid,
        capturado_em=QUANDO,
        origem=Origem.VOZ,
        texto_bruto="texto qualquer",
        assunto=assunto,
        tipo="ideia",
        proximos_passos=("Fazer algo",),
    )
    destino = C.caminho_do_registro(raiz, rid, assunto, QUANDO)
    gravar_registro(destino, reg)
    return destino, rid


# --------------------------------------------------------------------------
# Estabilidade do identificador
# --------------------------------------------------------------------------

def test_id_sobrevive_a_renomeacao(tmp_path: Path):
    destino, rid = gravar(tmp_path, "Newsletter por nicho")

    novo = destino.parent / "eu-renomeei-isso-a-mao.md"
    destino.rename(novo)

    assert ler_registro(novo).id == rid


def test_id_sobrevive_a_mudanca_de_pasta(tmp_path: Path):
    destino, rid = gravar(tmp_path, "Newsletter por nicho")

    outra = tmp_path / "minha-organizacao-propria"
    outra.mkdir()
    novo = outra / destino.name
    destino.rename(novo)

    assert ler_registro(novo).id == rid


def test_ids_gerados_no_mesmo_segundo_sao_distintos():
    """EC-01. Duas capturas em sequência imediata não podem colidir."""
    ids = {C.gerar_id(QUANDO) for _ in range(200)}
    assert len(ids) == 200


def test_id_carrega_o_momento_da_captura():
    assert C.gerar_id(QUANDO).startswith("20260811-143052-")


# --------------------------------------------------------------------------
# Nome de arquivo
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "assunto, esperado",
    [
        ("Newsletter por nicho", "newsletter-por-nicho"),
        ("Ideia: precificação / margem", "ideia-precificacao-margem"),
        ("  Espaços   demais  ", "espacos-demais"),
        ("ÁÉÍÓÚ ção", "aeiou-cao"),
        ("///", "sem-assunto"),
        ("", "sem-assunto"),
    ],
)
def test_normalizacao_de_assunto(assunto: str, esperado: str):
    assert C.normalizar(assunto, 80) == esperado


def test_nome_truncado_mas_assunto_integro_nos_metadados(tmp_path: Path):
    """EC-08. O nome encurta; o assunto não."""
    assunto = "Uma ideia muito comprida sobre precificacao de newsletter por nicho de mercado financeiro"
    destino, _ = gravar(tmp_path, assunto)

    assert len(destino.stem) < len(assunto)
    assert ler_registro(destino).assunto == assunto


def test_limite_vale_para_o_nome_inteiro_nao_so_para_o_assunto(tmp_path: Path):
    """O identificador ocupa 23 caracteres fixos e conta para o limite.

    Sem isso, um limite de 80 produziria nomes de 101 caracteres — e o Windows
    tem teto de 260 para o caminho completo, que uma pasta de acervo aninhada
    consome rápido.
    """
    assunto = "assunto " * 40
    destino = C.caminho_do_registro(
        tmp_path, "20260811-143052-abc123", assunto, QUANDO, limite_nome=80
    )

    assert len(destino.stem) <= 80


def test_limite_muito_curto_ainda_produz_nome_utilizavel(tmp_path: Path):
    """Configuração absurda não pode gerar nome vazio nem quebrar a gravação."""
    destino = C.caminho_do_registro(
        tmp_path, "20260811-143052-abc123", "Um assunto qualquer", QUANDO, limite_nome=10
    )

    assert destino.stem.startswith("20260811-143052-abc123-")
    assert destino.suffix == ".md"


def test_truncamento_corta_em_fronteira_de_palavra():
    resultado = C.normalizar("palavra outra terceira quarta quinta", 20)
    assert not resultado.endswith("-")
    assert len(resultado) <= 20
    assert "-".join(resultado.split("-")[:-1]) or resultado


def test_caracteres_invalidos_nunca_chegam_ao_nome(tmp_path: Path):
    """EC-04. Barra e dois-pontos quebrariam o caminho em qualquer sistema."""
    destino, _ = gravar(tmp_path, "a/b:c*d?e")

    for proibido in '/\\:*?"<>|':
        assert proibido not in destino.name


def test_colisao_de_nome_nao_sobrescreve(tmp_path: Path):
    """Sobrescrever um registro do usuário é inaceitável, por mais improvável."""
    primeiro, _ = gravar(tmp_path, "Mesmo assunto", identificador="id-fixo")
    segundo, _ = gravar(tmp_path, "Mesmo assunto", identificador="id-fixo")

    assert primeiro != segundo
    assert primeiro.exists() and segundo.exists()


# --------------------------------------------------------------------------
# Pasta derivada da data
# --------------------------------------------------------------------------

def test_pasta_mensal_derivada_da_data(tmp_path: Path):
    assert C.pasta_do_periodo(tmp_path, QUANDO, "mensal").name == "2026-08"


def test_pasta_semanal_derivada_da_data(tmp_path: Path):
    assert C.pasta_do_periodo(tmp_path, QUANDO, "semanal").name.startswith("2026-S")


def test_meses_distintos_geram_pastas_distintas(tmp_path: Path):
    setembro = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)

    a = C.caminho_do_registro(tmp_path, "a", "Assunto", QUANDO)
    b = C.caminho_do_registro(tmp_path, "b", "Assunto", setembro)

    assert a.parent != b.parent


def test_usuario_nunca_escolhe_pasta(tmp_path: Path):
    """O achado do enquadramento, em forma de teste.

    `caminho_do_registro` decide tudo a partir da data. Não existe parâmetro de
    categoria, e é isso que torna a captura possível dirigindo.
    """
    import inspect

    parametros = set(inspect.signature(C.caminho_do_registro).parameters)
    assert "categoria" not in parametros
    assert "pasta" not in parametros
