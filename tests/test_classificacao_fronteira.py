"""T016 — a fronteira de provedor é real.

Critério de aceite do RF-04, e ele é objetivo: **substituir o adaptador por uma
versão simulada não pode exigir alteração em nenhum outro arquivo.**

Isto é o que torna "qual provedor de linguagem?" uma pergunta não bloqueante.
Se a fronteira vazar — um `import` de fornecedor onde não devia, um campo
específico de provedor no contrato — a decisão volta a ser bloqueante e o
usuário passa a estar preso a quem escolheu no primeiro dia.

O teste mais importante deste arquivo é `test_fronteira_nao_importa_provedor`:
ele falha no dia em que alguém, com a melhor das intenções, "simplificar" o
código chamando o cliente do fornecedor direto da fronteira.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from memory_card.classificacao import adaptador as A
from memory_card.classificacao import erros as ERR
from memory_card.classificacao import fronteira as F
from memory_card.classificacao import validacao as V

TIPOS = ("ideia", "insight", "tarefa", "referencia", "duvida")


def pedido(texto: str = "gravar uma ideia sobre newsletter", **campos) -> F.PedidoClassificacao:
    base = dict(
        texto_bruto=texto,
        tipos_permitidos=TIPOS,
        prompt="prompt de teste",
        modelo="modelo-de-teste",
        timeout_s=15,
    )
    base.update(campos)
    return F.PedidoClassificacao(**base)


# --------------------------------------------------------------------------
# A fronteira não conhece provedor
# --------------------------------------------------------------------------

def test_fronteira_nao_importa_provedor():
    """Nenhum nome de fornecedor pode aparecer nos imports da fronteira."""
    arquivo = Path(F.__file__)
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))

    importados: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados += [a.name for a in no.names]
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.append(no.module)

    proibidos = ("anthropic", "openai", "google", "mistralai", "cohere", "ollama", "requests")
    vazamentos = [i for i in importados if any(p in i for p in proibidos)]
    assert not vazamentos, f"a fronteira vazou: {vazamentos}"


def test_trocar_de_adaptador_e_so_configuracao():
    """`LLM_PROVEDOR` decide, e nada mais no pipeline muda."""
    adaptador = F.obter_adaptador("simulado")
    resultado = adaptador.classificar(pedido())

    assert isinstance(resultado, F.Classificacao)
    assert resultado.tipo in TIPOS


def test_provedor_desconhecido_falha_nomeando_os_disponiveis():
    with pytest.raises(F.ProvedorDesconhecido) as erro:
        F.obter_adaptador("inexistente")

    assert "inexistente" in str(erro.value)
    assert "simulado" in str(erro.value)


def test_adaptador_concreto_esta_registrado():
    assert "anthropic" in F.adaptadores_disponiveis()
    assert "simulado" in F.adaptadores_disponiveis()


def test_pipeline_funciona_sem_o_pacote_do_provedor(monkeypatch):
    """Com o adaptador simulado, o pacote do fornecedor nunca é importado.

    É a forma mais direta de provar que a dependência está isolada: se algum
    ponto do caminho importasse o fornecedor, este teste quebraria.
    """
    import builtins

    original = builtins.__import__

    def recusar(nome, *args, **kwargs):
        if nome.split(".")[0] == "anthropic":
            raise AssertionError("o caminho simulado não pode importar o fornecedor")
        return original(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", recusar)

    resultado = F.obter_adaptador("simulado").classificar(pedido())
    assert resultado.assunto


# --------------------------------------------------------------------------
# Contrato de saída
# --------------------------------------------------------------------------

def test_adaptador_alternativo_satisfaz_o_contrato():
    """Qualquer objeto com `classificar` serve — é só isso que a fronteira exige."""

    class MeuProvedor:
        nome = "meu"

        def classificar(self, p: F.PedidoClassificacao) -> F.Classificacao:
            return V.validar(
                {
                    "assunto": "Vindo de outro provedor",
                    "tipo": "tarefa",
                    "proximos_passos": ["Conferir se funcionou"],
                },
                p.tipos_permitidos,
                F.Uso(provedor="meu", tokens_entrada=7, tokens_saida=3),
            )

    F.registrar("meu", lambda **o: MeuProvedor())
    resultado = F.obter_adaptador("meu").classificar(pedido())

    assert resultado.assunto == "Vindo de outro provedor"
    assert resultado.uso.provedor == "meu"
    assert resultado.uso.tokens_entrada == 7


def test_resposta_simulada_customizada():
    adaptador = A.AdaptadorSimulado(
        resposta=lambda p: {
            "assunto": "Fixo",
            "tipo": "duvida",
            "proximos_passos": ["Passo um", "Passo dois"],
            "multiplos_temas": True,
        }
    )
    resultado = adaptador.classificar(pedido())

    assert resultado.tipo == "duvida"
    assert len(resultado.proximos_passos) == 2
    assert resultado.multiplos_temas


# --------------------------------------------------------------------------
# Esquema imposto pelo provedor (RF-02a)
# --------------------------------------------------------------------------

def test_esquema_usa_o_conjunto_fechado_da_configuracao():
    """A configuração vira a própria garantia, não uma promessa."""
    esquema = A.montar_esquema(TIPOS)

    assert esquema["properties"]["tipo"]["enum"] == list(TIPOS)
    assert esquema["additionalProperties"] is False
    assert set(esquema["required"]) == {
        "assunto", "tipo", "proximos_passos", "multiplos_temas"
    }


def test_esquema_acompanha_uma_lista_de_tipos_diferente():
    esquema = A.montar_esquema(("nota", "acao"))
    assert esquema["properties"]["tipo"]["enum"] == ["nota", "acao"]


# --------------------------------------------------------------------------
# Validação portável (permanece obrigatória)
# --------------------------------------------------------------------------

def test_tipo_fora_do_conjunto_e_rejeitado():
    with pytest.raises(ERR.RespostaInvalida):
        V.validar(
            {"assunto": "x", "tipo": "categoria-inventada", "proximos_passos": ["a"]},
            TIPOS,
        )


def test_assunto_vazio_e_rejeitado():
    with pytest.raises(ERR.RespostaInvalida):
        V.validar({"assunto": "  ", "tipo": "ideia", "proximos_passos": ["a"]}, TIPOS)


def test_sem_proximos_passos_e_rejeitado():
    with pytest.raises(ERR.RespostaInvalida):
        V.validar({"assunto": "x", "tipo": "ideia", "proximos_passos": []}, TIPOS)


def test_json_em_cerca_de_codigo_e_aceito():
    """Resposta correta dentro de ```json não merece nova tentativa paga."""
    dados = V.extrair_json('```json\n{"assunto": "x", "tipo": "ideia"}\n```')
    assert dados["assunto"] == "x"


def test_texto_que_nao_e_json_vira_erro_nomeado():
    with pytest.raises(ERR.RespostaInvalida):
        V.extrair_json("desculpe, não consegui classificar isso")


def test_passo_vago_e_sinalizado_sem_rejeitar():
    """Diagnóstico, não bloqueio: rejeitar descartaria um registro por estilo."""
    resultado = V.validar(
        {
            "assunto": "x",
            "tipo": "ideia",
            "proximos_passos": ["Pensar melhor sobre isso", "Ligar para o fornecedor"],
        },
        TIPOS,
    )

    vagos = V.passos_vagos(resultado)
    assert len(vagos) == 1
    assert "Pensar melhor" in vagos[0]


# --------------------------------------------------------------------------
# Política de novas tentativas
# --------------------------------------------------------------------------

def test_erro_transitorio_e_repetido():
    tentativas = {"n": 0}

    def instavel():
        tentativas["n"] += 1
        if tentativas["n"] < 3:
            raise ERR.Indisponivel("caiu")
        return "ok"

    resultado = ERR.com_novas_tentativas(instavel, tentativas=3, dormir=lambda _: None)

    assert resultado == "ok"
    assert tentativas["n"] == 3


def test_cota_esgotada_nao_e_repetida():
    """Insistir não traz o saldo de volta — só queima tempo."""
    tentativas = {"n": 0}

    def sem_saldo():
        tentativas["n"] += 1
        raise ERR.CotaEsgotada("sem saldo")

    with pytest.raises(ERR.CotaEsgotada):
        ERR.com_novas_tentativas(sem_saldo, tentativas=3, dormir=lambda _: None)

    assert tentativas["n"] == 1


def test_conteudo_recusado_nao_e_repetido():
    def recusado():
        raise ERR.ConteudoRecusado("filtro do provedor")

    with pytest.raises(ERR.ConteudoRecusado):
        ERR.com_novas_tentativas(recusado, tentativas=3, dormir=lambda _: None)


def test_todo_erro_de_classificacao_tem_motivo_nomeado():
    """"Falhou ao classificar" não diz se é o arquivo, a cota ou a rede."""
    for classe in (
        ERR.Indisponivel, ERR.TempoExcedido, ERR.RespostaInvalida,
        ERR.CotaEsgotada, ERR.ConteudoRecusado, ERR.CredencialInvalida,
    ):
        assert classe.motivo and classe.motivo != "erro"
