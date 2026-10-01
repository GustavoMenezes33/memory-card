"""T017 — leitura nunca altera estado.

O requisito de integridade mais importante do sistema, verificado no nível HTTP.

Clientes de e-mail, antivírus e filtros de segurança **pré-carregam endereços**
contidos em mensagens. Se o link do digest alterasse o estado ao ser carregado,
essas ferramentas marcariam registros sozinhas e o usuário encontraria itens
"executados" que nunca tocou.

O dano não seria o registro errado: seria a perda de confiança. Um acervo que se
altera sozinho deixa de ser confiável inteiro, inclusive na parte correta — e o
produto existe justamente para o usuário confiar que o insight está guardado.

Este arquivo é o que impede alguém, no futuro, de "simplificar" o fluxo fazendo
o link marcar direto.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from memory_card import config as C
from memory_card.acervo import caminhos as CA
from memory_card.acervo import indice as IDX
from memory_card.acervo.escrita import gravar_registro
from memory_card.acervo.modelo import Estado, Origem, Registro
from memory_card.painel import confirmacao as CONF
from memory_card.painel.servidor import criar_app

BASE = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def acervo(ambiente_valido):
    """Configuração real com três registros gravados em disco."""
    cfg = C.carregar(env_file=None)
    C.garantir_diretorios(cfg)

    identificadores = []
    for indice, (assunto, estado) in enumerate(
        [("Primeiro", Estado.PENDENTE), ("Segundo", Estado.PENDENTE), ("Terceiro", Estado.EXECUTADO)]
    ):
        quando = BASE + timedelta(days=indice)
        rid = CA.gerar_id(quando)
        identificadores.append(rid)
        gravar_registro(
            CA.caminho_do_registro(cfg.acervo_pasta, rid, assunto, quando),
            Registro(
                id=rid,
                capturado_em=quando,
                origem=Origem.VOZ,
                texto_bruto=f"texto do {assunto.lower()}",
                assunto=assunto,
                tipo="ideia",
                proximos_passos=(f"Passo do {assunto.lower()}",),
                classificado=True,
                estado=estado,
            ),
        )
    IDX.reconstruir(cfg.acervo_pasta, cfg.acervo_indice_arquivo)
    return cfg, identificadores


def estado_de(cfg, identificador: str) -> str:
    entradas = IDX.reconstruir(cfg.acervo_pasta, cfg.acervo_indice_arquivo)
    return next(e for e in entradas if e.id == identificador).estado


# --------------------------------------------------------------------------
# A garantia central
# --------------------------------------------------------------------------

def test_get_na_pagina_de_confirmacao_nao_altera_estado(acervo):
    """Simula o pré-carregamento de link por um cliente de e-mail."""
    cfg, ids = acervo
    cliente = criar_app(cfg).test_client()
    alvo = ids[0]

    assert estado_de(cfg, alvo) == "pendente"

    resposta = cliente.get(f"/registro/{alvo}/marcar/executado")

    assert resposta.status_code == 200
    assert estado_de(cfg, alvo) == "pendente", "o carregamento alterou o estado"


def test_varios_gets_seguidos_nao_alteram_nada(acervo):
    """Antivírus e pré-visualização carregam o mesmo link mais de uma vez."""
    cfg, ids = acervo
    cliente = criar_app(cfg).test_client()
    alvo = ids[0]

    for _ in range(5):
        cliente.get(f"/registro/{alvo}/marcar/descartado")

    assert estado_de(cfg, alvo) == "pendente"


def test_post_altera_o_estado(acervo):
    cfg, ids = acervo
    cliente = criar_app(cfg).test_client()
    alvo = ids[0]

    resposta = cliente.post(f"/registro/{alvo}/marcar/executado")

    assert resposta.status_code == 200
    assert estado_de(cfg, alvo) == "executado"


def test_post_repetido_e_idempotente(acervo):
    """O usuário clica duas vezes quando a resposta demora."""
    cfg, ids = acervo
    cliente = criar_app(cfg).test_client()
    alvo = ids[0]

    cliente.post(f"/registro/{alvo}/marcar/executado")
    resposta = cliente.post(f"/registro/{alvo}/marcar/executado")

    assert resposta.status_code == 200
    assert estado_de(cfg, alvo) == "executado"


def test_marcar_como_descartado_depois_de_executado(acervo):
    """Mudar de ideia é operação válida, não erro."""
    cfg, ids = acervo
    cliente = criar_app(cfg).test_client()
    alvo = ids[0]

    cliente.post(f"/registro/{alvo}/marcar/executado")
    cliente.post(f"/registro/{alvo}/marcar/descartado")

    assert estado_de(cfg, alvo) == "descartado"


# --------------------------------------------------------------------------
# Casos que o usuário encontra na prática
# --------------------------------------------------------------------------

def test_link_de_registro_ja_marcado_explica_em_vez_de_falhar(acervo):
    """Digest antigo, registro já resolvido. Não pode dar erro."""
    cfg, ids = acervo
    cliente = criar_app(cfg).test_client()
    ja_executado = ids[2]

    resposta = cliente.get(f"/registro/{ja_executado}/marcar/executado")

    assert resposta.status_code == 200
    assert "já está marcado".encode() in resposta.data


def test_link_de_registro_apagado_a_mao_explica(acervo):
    """O usuário apagou o arquivo depois que o digest saiu."""
    cfg, _ = acervo
    cliente = criar_app(cfg).test_client()

    resposta = cliente.get("/registro/nao-existe-mais/marcar/executado")

    assert resposta.status_code == 200
    assert "não existe mais".encode() in resposta.data


def test_acao_desconhecida_e_recusada(acervo):
    cfg, ids = acervo
    cliente = criar_app(cfg).test_client()

    resposta = cliente.get(f"/registro/{ids[0]}/marcar/apagar")

    assert resposta.status_code == 400
    assert estado_de(cfg, ids[0]) == "pendente"


def test_post_com_acao_desconhecida_nao_altera_nada(acervo):
    cfg, ids = acervo
    cliente = criar_app(cfg).test_client()

    resposta = cliente.post(f"/registro/{ids[0]}/marcar/apagar")

    assert resposta.status_code == 400
    assert estado_de(cfg, ids[0]) == "pendente"


# --------------------------------------------------------------------------
# O contrato do endereço
# --------------------------------------------------------------------------

def test_url_de_marcacao_tem_formato_estavel():
    """Estes endereços ficam gravados em e-mails que o usuário guarda.

    Mudar o formato quebra digests já enviados, então ele tem estabilidade de
    contrato público mesmo nunca saindo da máquina.
    """
    url = CONF.url_de_marcacao("http://localhost:8000", "abc-123", "executado")

    assert url == "http://localhost:8000/registro/abc-123/marcar/executado"


def test_url_de_marcacao_tolera_barra_final():
    url = CONF.url_de_marcacao("http://localhost:8000/", "abc", "descartado")

    assert "//registro" not in url


def test_pagina_individual_do_registro_abre(acervo):
    cfg, ids = acervo
    cliente = criar_app(cfg).test_client()

    resposta = cliente.get(f"/registro/{ids[0]}")

    assert resposta.status_code == 200
    assert "Primeiro".encode() in resposta.data
    assert "texto do primeiro".encode() in resposta.data


def test_painel_inicial_abre_com_acervo_vazio(ambiente_valido):
    """Estado vazio é informação legítima, não erro."""
    cfg = C.carregar(env_file=None)
    C.garantir_diretorios(cfg)
    cliente = criar_app(cfg).test_client()

    resposta = cliente.get("/")

    assert resposta.status_code == 200
    assert "Nenhum registro ainda".encode() in resposta.data
