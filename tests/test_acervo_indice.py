"""O índice não pode congelar.

Regressão de um defeito encontrado na primeira captura real: o índice era
escrito uma única vez, quando ainda não existia, e nunca mais. Como ele é a
origem da listagem do painel e da seleção do digest, as capturas seguintes
existiam em disco e não apareciam em lugar nenhum — nem na tela, nem no e-mail
de domingo. O acervo estava íntegro e o produto parecia vazio.

O que estes testes protegem é a promessa do módulo: **o arquivo em disco é a
fonte da verdade, o índice é só um atalho.** Um atalho que discorda do disco é
pior que nenhum atalho.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from memory_card import config as C
from memory_card.acervo import caminhos as CA
from memory_card.acervo import indice as IDX
from memory_card.acervo.escrita import gravar_registro
from memory_card.acervo.estado import alterar_estado
from memory_card.acervo.modelo import Estado, Origem, Registro

BASE = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def cfg(ambiente_valido):
    configuracao = C.carregar(env_file=None)
    C.garantir_diretorios(configuracao)
    return configuracao


def gravar(cfg, assunto: str, dias: int = 0, estado: Estado = Estado.PENDENTE) -> str:
    quando = BASE + timedelta(days=dias)
    rid = CA.gerar_id(quando)
    gravar_registro(
        CA.caminho_do_registro(cfg.acervo_pasta, rid, assunto, quando),
        Registro(
            id=rid,
            capturado_em=quando,
            origem=Origem.VOZ,
            texto_bruto=f"texto de {assunto}",
            assunto=assunto,
            tipo="ideia",
            proximos_passos=(f"Passo de {assunto}",),
            classificado=True,
            estado=estado,
        ),
    )
    return rid


# --------------------------------------------------------------------------
# O defeito que motivou o arquivo
# --------------------------------------------------------------------------

def test_registro_gravado_depois_do_indice_aparece(cfg):
    """O caso exato do defeito: índice criado com o acervo vazio.

    É o que acontece quando o usuário abre o painel antes da primeira captura,
    que é justamente o que o guia de configuração manda fazer.
    """
    assert IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta) == []
    assert cfg.acervo_indice_arquivo.exists()

    gravar(cfg, "Primeira captura")

    entradas = IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)
    assert [e.assunto for e in entradas] == ["Primeira captura"]


def test_capturas_sucessivas_aparecem_todas(cfg):
    esperados = []
    for numero in range(1, 4):
        esperados.append(f"Captura {numero}")
        gravar(cfg, f"Captura {numero}", dias=numero)
        entradas = IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)
        assert [e.assunto for e in entradas] == esperados


def test_mudanca_de_estado_aparece_no_indice(cfg):
    """A marcação vinda do digest precisa refletir na listagem do painel."""
    rid = gravar(cfg, "Virou ação")
    entradas = IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)
    assert entradas[0].estado == "pendente"

    caminho = cfg.acervo_pasta / entradas[0].caminho
    alterar_estado(caminho, Estado.EXECUTADO, esperado=rid)

    entradas = IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)
    assert entradas[0].estado == "executado"


def test_registro_apagado_a_mao_some_do_indice(cfg):
    """Apagar um markdown no explorador de arquivos é edição legítima."""
    gravar(cfg, "Arrependimento")
    entradas = IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)
    assert len(entradas) == 1

    (cfg.acervo_pasta / entradas[0].caminho).unlink()

    assert IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta) == []


# --------------------------------------------------------------------------
# Propriedades que já valiam e precisam continuar valendo
# --------------------------------------------------------------------------

def test_indice_intacto_nao_e_reconstruido(cfg, monkeypatch):
    """Sem mudança no acervo, ler o índice não custa uma varredura completa.

    Se a verificação de idade sempre reconstruísse, o índice deixaria de ser
    atalho e viraria enfeite: toda visita ao painel pagaria a leitura de todos
    os registros.
    """
    gravar(cfg, "Estável")
    IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)

    def falhar(*_args, **_kwargs):
        raise AssertionError("reconstruiu um índice que estava em dia")

    monkeypatch.setattr(IDX, "construir", falhar)
    entradas = IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)
    assert [e.assunto for e in entradas] == ["Estável"]


def test_indice_corrompido_se_regenera(cfg):
    gravar(cfg, "Sobrevivente")
    IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)
    cfg.acervo_indice_arquivo.write_text("{lixo", encoding="utf-8")

    entradas = IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)
    assert [e.assunto for e in entradas] == ["Sobrevivente"]


def test_reconstruir_e_deterministico(cfg):
    """EC-07: apagar o índice e reconstruir produz exatamente o mesmo arquivo."""
    gravar(cfg, "Um", dias=0)
    gravar(cfg, "Dois", dias=1)

    IDX.reconstruir(cfg.acervo_pasta, cfg.acervo_indice_arquivo)
    primeiro = cfg.acervo_indice_arquivo.read_bytes()

    cfg.acervo_indice_arquivo.unlink()
    IDX.reconstruir(cfg.acervo_pasta, cfg.acervo_indice_arquivo)

    assert cfg.acervo_indice_arquivo.read_bytes() == primeiro


def test_indice_nao_guarda_texto_bruto(cfg):
    """Duplicar o conteúdo criaria uma segunda cópia capaz de divergir."""
    gravar(cfg, "Sigiloso")
    IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)

    dados = json.loads(cfg.acervo_indice_arquivo.read_text(encoding="utf-8"))
    assert "texto de Sigiloso" not in json.dumps(dados, ensure_ascii=False)
