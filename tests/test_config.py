"""T011 — parâmetros obrigatórios.

Verifica RF-16 do requirements e a garantia O-001/O-002 do regression-watch:
a ausência de qualquer obrigatório impede a inicialização e nomeia o parâmetro
faltante, e em nenhuma hipótese o sistema entra em modo permissivo.
"""

from __future__ import annotations

import pytest

from memory_card import config as C
from tests.conftest import BASE_VALIDA


def test_ambiente_valido_inicia(ambiente_valido):
    cfg = C.carregar(env_file=None)
    assert cfg.telegram_usuario_autorizado == 42
    assert cfg.llm_provedor == "provedor-de-teste"


@pytest.mark.parametrize("ausente", sorted(BASE_VALIDA))
def test_obrigatorio_ausente_impede_inicializacao(ambiente_valido, ausente):
    """Cada obrigatório, um a um. Falhar é o comportamento correto."""
    ambiente_valido.delenv(ausente, raising=False)

    with pytest.raises(C.ConfiguracaoInvalida) as erro:
        C.carregar(env_file=None)

    # O erro precisa NOMEAR o parâmetro. Um erro genérico obriga o usuário
    # a caçar, e caçar é o que faz alguém desistir de configurar direito.
    assert ausente in str(erro.value)


def test_obrigatorio_vazio_conta_como_ausente(ambiente_valido):
    """String vazia não é valor. Preencher com "" não pode passar."""
    ambiente_valido.setenv("LLM_API_KEY", "   ")

    with pytest.raises(C.ConfiguracaoInvalida) as erro:
        C.carregar(env_file=None)

    assert "LLM_API_KEY" in str(erro.value)


def test_erro_nomeia_todos_os_ausentes_de_uma_vez(ambiente_valido):
    """Relatar um por vez obrigaria a reiniciar oito vezes."""
    for chave in ("LLM_API_KEY", "SMTP_SERVIDOR", "TELEGRAM_BOT_TOKEN"):
        ambiente_valido.delenv(chave, raising=False)

    with pytest.raises(C.ConfiguracaoInvalida) as erro:
        C.carregar(env_file=None)

    mensagem = str(erro.value)
    assert "LLM_API_KEY" in mensagem
    assert "SMTP_SERVIDOR" in mensagem
    assert "TELEGRAM_BOT_TOKEN" in mensagem


def test_usuario_autorizado_vazio_nunca_vira_modo_permissivo(ambiente_valido):
    """O-002. A garantia mais importante deste arquivo.

    Campo vazio jamais pode significar "aceitar qualquer remetente": seria um
    bot aberto a quem descobrisse seu nome, com conteúdo de origem desconhecida
    entrando no acervo.
    """
    ambiente_valido.setenv("TELEGRAM_USUARIO_AUTORIZADO", "")

    with pytest.raises(C.ConfiguracaoInvalida):
        C.carregar(env_file=None)


def test_usuario_autorizado_nao_numerico_e_recusado(ambiente_valido):
    ambiente_valido.setenv("TELEGRAM_USUARIO_AUTORIZADO", "@gustavo")

    with pytest.raises(C.ConfiguracaoInvalida) as erro:
        C.carregar(env_file=None)

    assert "TELEGRAM_USUARIO_AUTORIZADO" in str(erro.value)


def test_padroes_aplicados_quando_opcionais_ausentes(ambiente_valido):
    """Só os oito obrigatórios são exigidos; o resto tem padrão."""
    cfg = C.carregar(env_file=None)

    assert cfg.whisper_modelo == "small"
    assert cfg.smtp_porta == 587
    assert cfg.digest_quantidade == 5
    assert cfg.digest_horario == (19, 0)
    assert cfg.digest_dia_semana == 4          # sexta
    assert cfg.audio_longo_limite_s == 180
    assert cfg.llm_tipos_registro == (
        "ideia", "insight", "tarefa", "referencia", "duvida",
    )


def test_padrao_do_digest_nao_cai_no_ultimo_dia_da_semana(ambiente_valido):
    """O dia padrão precisa deixar janela de recuperação.

    O envio não é reposto na semana seguinte: quem perde o horário só tem até a
    virada da semana ISO, na meia-noite de domingo. Um padrão em `domingo`
    deixaria cinco horas — uma noite fora de casa custaria o digest inteiro.
    Este teste existe para que uma mudança de padrão nesse sentido seja uma
    decisão consciente, e não um detalhe que passa despercebido.
    """
    cfg = C.carregar(env_file=None)

    assert cfg.digest_dia_semana < 6, (
        "o padrão caiu em domingo, o último dia da semana ISO: a janela de "
        "recuperação encolhe para as horas entre o horário marcado e a "
        "meia-noite"
    )


def test_valor_nao_numerico_em_campo_inteiro_nomeia_o_campo(ambiente_valido):
    ambiente_valido.setenv("DIGEST_QUANTIDADE", "cinco")

    with pytest.raises(C.ConfiguracaoInvalida) as erro:
        C.carregar(env_file=None)

    assert "DIGEST_QUANTIDADE" in str(erro.value)


@pytest.mark.parametrize("valor", ["25:00", "19h", "19", "19:99"])
def test_horario_invalido_e_recusado(ambiente_valido, valor):
    ambiente_valido.setenv("DIGEST_HORARIO", valor)

    with pytest.raises(C.ConfiguracaoInvalida) as erro:
        C.carregar(env_file=None)

    assert "DIGEST_HORARIO" in str(erro.value)


def test_granularidade_de_pasta_restrita_aos_valores_previstos(ambiente_valido):
    ambiente_valido.setenv("ACERVO_GRANULARIDADE_PASTA", "diaria")

    with pytest.raises(C.ConfiguracaoInvalida) as erro:
        C.carregar(env_file=None)

    assert "ACERVO_GRANULARIDADE_PASTA" in str(erro.value)


def test_criacao_de_diretorios_e_idempotente(ambiente_valido):
    """O-006. Cria o que falta e nunca toca em arquivo."""
    cfg = C.carregar(env_file=None)

    criados = C.garantir_diretorios(cfg)
    assert criados, "esperava criar as pastas de dados na primeira execução"
    assert all(caminho.is_dir() for caminho in criados)

    assert C.garantir_diretorios(cfg) == [], "segunda execução não deve criar nada"
