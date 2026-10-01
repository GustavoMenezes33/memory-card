"""T012 — exposição de rede do painel e coerência com o digest.

Verifica RF-15 e RF-19 do requirements, e as garantias O-003, O-004 e O-005
do regression-watch.

Duas regras com severidades deliberadamente diferentes:

- Interface fora de loopback **impede** a inicialização. O acervo é o dado
  mais sensível do sistema e o único que permanece local; publicá-lo por erro
  de configuração é pior que não subir o painel.
- Divergência entre o endereço do painel e o usado nos links do digest apenas
  **alerta**. O painel funciona; o que quebra são os links de digests já
  enviados, que estão na caixa de e-mail do usuário. Impedir a inicialização
  seria desproporcional, e silenciar produziria um digest íntegro com todos os
  links apontando para lugar nenhum.
"""

from __future__ import annotations

import pytest

from memory_card import config as C


# --------------------------------------------------------------------------
# O-003: só loopback
# --------------------------------------------------------------------------

@pytest.mark.parametrize("interface", ["127.0.0.1", "localhost", "::1", "127.0.0.5"])
def test_loopback_e_aceito(ambiente_valido, interface):
    ambiente_valido.setenv("PAINEL_INTERFACE", interface)
    ambiente_valido.setenv("PAINEL_URL_BASE", "http://localhost:8000")

    cfg = C.carregar(env_file=None)
    assert cfg.painel_interface == interface


@pytest.mark.parametrize(
    "interface",
    ["0.0.0.0", "192.168.0.10", "10.0.0.1", "203.0.113.7", "::", "nao-e-um-endereco"],
)
def test_interface_externa_impede_inicializacao(ambiente_valido, interface):
    ambiente_valido.setenv("PAINEL_INTERFACE", interface)

    with pytest.raises(C.ConfiguracaoInvalida) as erro:
        C.carregar(env_file=None)

    assert "PAINEL_INTERFACE" in str(erro.value)


def test_endereco_de_escuta_geral_e_recusado(ambiente_valido):
    """`0.0.0.0` é o valor que alguém escreve por hábito e publica o acervo."""
    ambiente_valido.setenv("PAINEL_INTERFACE", "0.0.0.0")

    with pytest.raises(C.ConfiguracaoInvalida) as erro:
        C.carregar(env_file=None)

    assert "loopback" in str(erro.value).lower()


# --------------------------------------------------------------------------
# O-004 e O-005: coerência entre painel e digest
# --------------------------------------------------------------------------

def test_padroes_concordam_por_construcao(ambiente_valido):
    """O-005. Com o `.env` sem sobrescrita, os dois lados coincidem."""
    cfg = C.carregar(env_file=None)

    assert cfg.painel_porta == 8000
    assert cfg.painel_interface == "127.0.0.1"
    assert cfg.painel_url_base == "http://localhost:8000"
    assert cfg.alertas == (), f"não esperava alerta nos padrões: {cfg.alertas}"


def test_porta_divergente_alerta_mas_nao_impede(ambiente_valido):
    """O-004. Alerta e inicia — a divergência não é fatal, é silenciosa."""
    ambiente_valido.setenv("PAINEL_PORTA", "9999")

    cfg = C.carregar(env_file=None)

    assert cfg.painel_porta == 9999
    assert len(cfg.alertas) == 1
    alerta = cfg.alertas[0]
    assert "PAINEL_URL_BASE" in alerta
    assert "9999" in alerta


def test_url_base_com_host_estranho_alerta(ambiente_valido):
    ambiente_valido.setenv("PAINEL_URL_BASE", "http://meu-servidor.example.com:8000")

    cfg = C.carregar(env_file=None)

    assert cfg.alertas, "host diferente do de escuta precisa alertar"


def test_url_base_malformada_alerta_sem_derrubar(ambiente_valido):
    ambiente_valido.setenv("PAINEL_URL_BASE", "localhost-8000")

    cfg = C.carregar(env_file=None)

    assert cfg.alertas
    assert "PAINEL_URL_BASE" in cfg.alertas[0]


def test_porta_explicita_coerente_nao_alerta(ambiente_valido):
    ambiente_valido.setenv("PAINEL_PORTA", "8123")
    ambiente_valido.setenv("PAINEL_URL_BASE", "http://127.0.0.1:8123")

    cfg = C.carregar(env_file=None)

    assert cfg.alertas == ()


def test_barra_final_na_url_base_e_normalizada(ambiente_valido):
    """Sem isso, os links do digest sairiam com barra dupla."""
    ambiente_valido.setenv("PAINEL_URL_BASE", "http://localhost:8000/")

    cfg = C.carregar(env_file=None)

    assert cfg.painel_url_base == "http://localhost:8000"
    assert cfg.alertas == ()
