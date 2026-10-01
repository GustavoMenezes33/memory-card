"""T018 — seleção do digest: mais antigos primeiro, limite respeitado.

A regra é deliberadamente burra, e os testes protegem justamente a burrice: no
dia em que alguém acrescentar "inteligência" na seleção sem decisão explícita,
estes testes quebram.

Mais antigos primeiro faz o acervo drenar de verdade — nada apodrece no fundo.
O custo é conhecido e aceito: os primeiros envios trazem ideias velhas e o
descarte inicial é alto, o que é saudável, não fracasso.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from memory_card.acervo.indice import EntradaIndice
from memory_card.digest import montagem as MO
from memory_card.digest.selecao import selecionar

BASE = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)


def entrada(
    identificador: str,
    dias: int,
    estado: str = "pendente",
    assunto: str = "",
    classificado: bool = True,
    origem: str = "voz",
) -> EntradaIndice:
    quando = BASE + timedelta(days=dias)
    return EntradaIndice(
        id=identificador,
        caminho=f"2026-08/{identificador}.md",
        capturado_em=quando.isoformat(timespec="seconds"),
        assunto=assunto or f"Assunto {identificador}",
        tipo="ideia",
        estado=estado,
        origem=origem,
        classificado=classificado,
        contem_terceiros=origem == "reuniao",
    )


# --------------------------------------------------------------------------
# Ordem e limite
# --------------------------------------------------------------------------

def test_mais_antigos_primeiro():
    entradas = [entrada("c", 20), entrada("a", 0), entrada("b", 10)]

    selecao = selecionar(entradas, limite=3)

    assert [e.id for e in selecao.incluidos] == ["a", "b", "c"]


def test_limite_e_respeitado():
    entradas = [entrada(str(i), i) for i in range(20)]

    selecao = selecionar(entradas, limite=5)

    assert len(selecao.incluidos) == 5
    assert selecao.total_pendentes == 20
    assert selecao.restantes == 15


def test_limite_maior_que_o_acervo_traz_todos():
    entradas = [entrada("a", 0), entrada("b", 1)]

    selecao = selecionar(entradas, limite=10)

    assert len(selecao.incluidos) == 2
    assert selecao.restantes == 0


def test_limite_zero_nao_quebra():
    selecao = selecionar([entrada("a", 0)], limite=0)

    assert selecao.vazia
    assert selecao.total_pendentes == 1


def test_ordem_independe_da_ordem_de_entrada():
    """A seleção é determinística: o mesmo acervo produz sempre o mesmo envio."""
    entradas = [entrada("z", 5), entrada("y", 1), entrada("x", 3)]

    primeira = selecionar(entradas, limite=2)
    segunda = selecionar(list(reversed(entradas)), limite=2)

    assert [e.id for e in primeira.incluidos] == [e.id for e in segunda.incluidos]


# --------------------------------------------------------------------------
# Só pendentes
# --------------------------------------------------------------------------

def test_executados_nao_reaparecem():
    entradas = [
        entrada("feito", 0, estado="executado"),
        entrada("pendente", 5),
    ]

    selecao = selecionar(entradas, limite=10)

    assert [e.id for e in selecao.incluidos] == ["pendente"]


def test_descartados_nao_reaparecem():
    """Descartar é definitivo: o registro não volta a incomodar."""
    entradas = [
        entrada("lixo", 0, estado="descartado"),
        entrada("pendente", 5),
    ]

    selecao = selecionar(entradas, limite=10)

    assert [e.id for e in selecao.incluidos] == ["pendente"]


def test_total_pendentes_ignora_resolvidos():
    entradas = [
        entrada("a", 0),
        entrada("b", 1, estado="executado"),
        entrada("c", 2, estado="descartado"),
    ]

    selecao = selecionar(entradas, limite=10)

    assert selecao.total_pendentes == 1


def test_acervo_todo_resolvido_gera_selecao_vazia():
    entradas = [entrada("a", 0, estado="executado"), entrada("b", 1, estado="descartado")]

    selecao = selecionar(entradas, limite=5)

    assert selecao.vazia
    assert selecao.total_pendentes == 0


def test_registro_nao_classificado_entra_no_digest():
    """Um registro sem estrutura ainda pode gerar ação."""
    entradas = [entrada("sem-estrutura", 0, classificado=False)]

    selecao = selecionar(entradas, limite=5)

    assert len(selecao.incluidos) == 1


# --------------------------------------------------------------------------
# O e-mail montado a partir da seleção
# --------------------------------------------------------------------------

def test_corpo_traz_os_dois_links_por_registro():
    selecao = selecionar([entrada("abc", 0)], limite=5)

    corpo = MO.corpo_texto(selecao, "http://localhost:8000")

    assert "/registro/abc/marcar/executado" in corpo
    assert "/registro/abc/marcar/descartado" in corpo


def test_corpo_informa_o_total_de_pendentes():
    """É como o usuário percebe acúmulo sem abrir o painel."""
    entradas = [entrada(str(i), i) for i in range(30)]
    selecao = selecionar(entradas, limite=5)

    corpo = MO.corpo_texto(selecao, "http://localhost:8000")

    assert "30 registros pendentes" in corpo
    assert "25" in corpo


def test_corpo_avisa_que_abrir_o_link_nao_marca():
    corpo = MO.corpo_texto(selecionar([entrada("a", 0)], limite=5), "http://x")

    assert "confirmar" in corpo


def test_selecao_vazia_ainda_gera_e_mail():
    """Silêncio seria indistinguível de falha."""
    selecao = selecionar([], limite=5)

    corpo = MO.corpo_texto(selecao, "http://localhost:8000")
    assunto = MO.assunto_do_email(selecao, BASE)

    assert "Nenhum registro pendente" in corpo
    assert "nada pendente" in assunto


def test_reuniao_e_marcada_no_corpo():
    """RN-09: o usuário precisa saber que aquele registro tem fala de terceiros."""
    selecao = selecionar([entrada("r", 0, origem="reuniao")], limite=5)

    corpo = MO.corpo_texto(selecao, "http://x")

    assert "reunião" in corpo


def test_nao_classificado_e_marcado_no_corpo():
    selecao = selecionar([entrada("n", 0, classificado=False)], limite=5)

    corpo = MO.corpo_texto(selecao, "http://x")

    assert "não classificado" in corpo


def test_html_e_texto_cobrem_os_mesmos_registros():
    """O e-mail precisa ser legível com imagens bloqueadas."""
    selecao = selecionar([entrada("a", 0, assunto="Newsletter"), entrada("b", 1)], limite=5)

    texto = MO.corpo_texto(selecao, "http://x")
    html = MO.corpo_html(selecao, "http://x")

    for identificador in ("a", "b"):
        assert f"/registro/{identificador}/marcar/executado" in texto
        assert f"/registro/{identificador}/marcar/executado" in html
    assert "Newsletter" in texto and "Newsletter" in html


def test_assunto_do_email_usa_singular_e_plural():
    um = MO.assunto_do_email(selecionar([entrada("a", 0)], limite=5), BASE)
    dois = MO.assunto_do_email(selecionar([entrada("a", 0), entrada("b", 1)], limite=5), BASE)

    assert "1 registro " in um
    assert "2 registros " in dois
