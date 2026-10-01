"""Comando do Telegram não é captura.

Regressão de um defeito encontrado na primeira captura real: o `/start` — que
todo usuário manda, porque é o botão que abre a conversa com o bot — entrou na
esteira como texto comum. Gastou uma chamada de API e virou um registro no
acervo com assunto "áudio vazio, sem conteúdo transcrito", inventado pelo
modelo, que descreve um áudio que nunca existiu.

Dois danos distintos, e o segundo é o que importa: lixo no acervo compete com
insight de verdade na seleção do digest, que leva só cinco por semana.
"""

from __future__ import annotations

import pytest

from memory_card import app as A
from memory_card import config as C
from memory_card.captura.respostas import resposta_a_comando
from memory_card.captura.texto import e_comando
from memory_card.esteira import Esteira, item_de_mensagem

USUARIO = 42


class ClienteFalso:
    """Registra o que seria enviado ao chat, sem tocar na rede."""

    def __init__(self) -> None:
        self.enviadas: list[str] = []

    def enviar_mensagem(self, chat_id: int, texto: str) -> None:
        self.enviadas.append(texto)


class ExecutorFalso:
    """Qualquer uso aqui é o defeito: comando não pode chegar à esteira."""

    def enfileirar(self, item):
        raise AssertionError("comando foi enfileirado")

    def processar_um(self, item):
        raise AssertionError("comando foi processado")


def mensagem_de_texto(texto: str, message_id: int = 1) -> dict:
    return {
        "message_id": message_id,
        "from": {"id": USUARIO},
        "chat": {"id": USUARIO},
        "text": texto,
    }


@pytest.fixture
def cenario(ambiente_valido):
    cfg = C.carregar(env_file=None)
    C.garantir_diretorios(cfg)
    cliente = ClienteFalso()
    esteira = Esteira(cfg=cfg, cliente=cliente, adaptador=None, conversas={})
    return cfg, esteira, cliente, ExecutorFalso()


# --------------------------------------------------------------------------
# Reconhecimento
# --------------------------------------------------------------------------

@pytest.mark.parametrize("texto", ["/start", "/help", "  /start  ", "/start@meu_bot"])
def test_reconhece_comando(texto):
    assert e_comando(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "lembrar de olhar o Apache Spark",
        "e/ou testar a hipótese",       # barra no meio não é comando
        "",
        None,
    ],
)
def test_nao_confunde_captura_com_comando(texto):
    assert not e_comando(texto)


# --------------------------------------------------------------------------
# O comando não entra na esteira
# --------------------------------------------------------------------------

def test_start_nao_e_enfileirado_nem_arquivado(cenario):
    cfg, esteira, cliente, executor = cenario

    A.processar(cfg, esteira, executor, mensagem_de_texto("/start"))

    # O ExecutorFalso levanta se for tocado; chegar aqui já é metade do teste.
    assert list(cfg.acervo_pasta.rglob("*.md")) == []
    assert list(cfg.fila_pasta.glob("*.json")) == []


def test_start_recebe_resposta_que_explica(cenario):
    _cfg, esteira, cliente, executor = cenario

    A.processar(_cfg, esteira, executor, mensagem_de_texto("/start"))

    assert len(cliente.enviadas) == 1
    assert "não viram registro" in cliente.enviadas[0]


def test_comando_desconhecido_tambem_e_recusado(cenario):
    cfg, esteira, cliente, executor = cenario

    A.processar(cfg, esteira, executor, mensagem_de_texto("/configurar"))

    assert len(cliente.enviadas) == 1
    assert list(cfg.acervo_pasta.rglob("*.md")) == []


def test_texto_comum_continua_virando_item(cenario):
    """A porta fechada para comandos não pode fechar a captura por texto."""
    mensagem = mensagem_de_texto("preciso verificar o Apache Spark", message_id=7)
    item = item_de_mensagem(f"{USUARIO}-7", mensagem)

    assert item is not None
    assert item.texto_bruto == "preciso verificar o Apache Spark"
    assert item.tipo_origem == "texto"


def test_resposta_ao_start_orienta_o_proximo_passo():
    texto = resposta_a_comando("/start")
    assert "voz" in texto and "texto" in texto
