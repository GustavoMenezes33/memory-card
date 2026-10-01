"""T030 — adaptadores concretos.

Este é o **único** arquivo do sistema que conhece um provedor. Trocar de
fornecedor é escrever um irmão deste arquivo e mudar `LLM_PROVEDOR` no `.env`;
nada mais no pipeline muda. Esse é o critério de aceite do RF-04, e é o que
mantém a escolha de provedor adiável sem custo.

Duas implementações nascem aqui:

- `AdaptadorAnthropic`, o concreto, que usa **imposição de esquema pelo
  provedor** (RF-02a). Com o esquema declarado na requisição, o modelo não
  consegue devolver tipo fora da lista: o EC-03 deixa de ser um caso de erro
  tratado por nova tentativa e passa a ser impossível por construção. A
  validação de `validacao.py` continua obrigatória mesmo assim — ela é o piso
  portável para provedores sem o recurso.
- `AdaptadorSimulado`, que existe para o T016 provar que substituir o adaptador
  não exige alteração em nenhum outro arquivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .erros import (
    ConteudoRecusado,
    CotaEsgotada,
    CredencialInvalida,
    Indisponivel,
    RespostaInvalida,
    TempoExcedido,
)
from .fronteira import Classificacao, PedidoClassificacao, Uso, registrar
from .validacao import extrair_json, validar


def montar_esquema(tipos_permitidos: tuple[str, ...]) -> dict:
    """O conjunto fechado de `LLM_TIPOS_REGISTRO` vira a enumeração do esquema.

    É aqui que a configuração deixa de ser uma promessa e passa a ser a própria
    garantia: o valor do `.env` alimenta diretamente o que o provedor aceita.
    """
    return {
        "type": "object",
        "properties": {
            "assunto": {"type": "string"},
            "tipo": {"type": "string", "enum": list(tipos_permitidos)},
            "proximos_passos": {"type": "array", "items": {"type": "string"}},
            "multiplos_temas": {"type": "boolean"},
        },
        "required": ["assunto", "tipo", "proximos_passos", "multiplos_temas"],
        "additionalProperties": False,
    }


# --------------------------------------------------------------------------
# Adaptador concreto
# --------------------------------------------------------------------------

@dataclass
class AdaptadorAnthropic:
    api_key: str
    endpoint: str = ""
    nome: str = "anthropic"
    _cliente: object | None = None

    def _obter_cliente(self):
        """Importação tardia: o pacote só é exigido quando há o que classificar."""
        if self._cliente is not None:
            return self._cliente
        try:
            import anthropic
        except ImportError as erro:  # pragma: no cover - depende do ambiente
            raise CredencialInvalida(
                "o pacote 'anthropic' não está instalado. Instale as "
                "dependências do projeto antes de classificar."
            ) from erro

        opcoes: dict[str, object] = {"api_key": self.api_key}
        if self.endpoint:
            opcoes["base_url"] = self.endpoint
        self._cliente = anthropic.Anthropic(**opcoes)
        return self._cliente

    def classificar(self, pedido: PedidoClassificacao) -> Classificacao:
        import anthropic

        cliente = self._obter_cliente()
        instrucao = pedido.prompt
        if pedido.multiplos_passos:
            instrucao += (
                "\n\nEste áudio é longo e provavelmente contém vários assuntos. "
                "Liste um próximo passo por tema relevante."
            )

        try:
            resposta = cliente.with_options(timeout=pedido.timeout_s).messages.create(
                model=pedido.modelo,
                max_tokens=8000,
                system=instrucao,
                messages=[{"role": "user", "content": pedido.texto_bruto}],
                output_config={
                    "effort": "low",   # extração estruturada, não raciocínio profundo
                    "format": {
                        "type": "json_schema",
                        "schema": montar_esquema(pedido.tipos_permitidos),
                    },
                },
            )
        except anthropic.AuthenticationError as erro:
            raise CredencialInvalida(f"chave de API rejeitada: {erro}") from erro
        except anthropic.PermissionDeniedError as erro:
            raise CredencialInvalida(f"chave sem permissão: {erro}") from erro
        except anthropic.NotFoundError as erro:
            raise CredencialInvalida(
                f"modelo {pedido.modelo!r} não encontrado: {erro}"
            ) from erro
        except anthropic.RateLimitError as erro:
            # Distinto de indisponibilidade: a causa pode ser financeira, e
            # confundir as duas manda o usuário depurar a rede por engano.
            raise CotaEsgotada(f"limite de uso atingido: {erro}") from erro
        except anthropic.APITimeoutError as erro:
            raise TempoExcedido(f"tempo excedido ao classificar: {erro}") from erro
        except anthropic.APIConnectionError as erro:
            raise Indisponivel(f"falha de conexão com o provedor: {erro}") from erro
        except anthropic.APIStatusError as erro:
            if erro.status_code >= 500:
                raise Indisponivel(f"provedor indisponível: {erro}") from erro
            raise RespostaInvalida(f"requisição rejeitada: {erro}") from erro

        # Um recusa de política volta como HTTP 200 com conteúdo vazio. Ler
        # content[0] direto aqui quebraria; e o registro do usuário jamais pode
        # ser descartado por decisão de terceiro.
        if getattr(resposta, "stop_reason", None) == "refusal":
            detalhes = getattr(resposta, "stop_details", None)
            categoria = getattr(detalhes, "category", None) or "não informada"
            raise ConteudoRecusado(
                f"o provedor recusou classificar este registro (categoria: {categoria})"
            )

        texto = next(
            (b.text for b in resposta.content if getattr(b, "type", "") == "text"),
            "",
        )
        if not texto.strip():
            raise RespostaInvalida("o provedor devolveu resposta sem conteúdo")

        uso_bruto = getattr(resposta, "usage", None)
        uso = Uso(
            provedor=self.nome,
            modelo=getattr(resposta, "model", pedido.modelo),
            tokens_entrada=getattr(uso_bruto, "input_tokens", 0) or 0,
            tokens_saida=getattr(uso_bruto, "output_tokens", 0) or 0,
        )
        return validar(extrair_json(texto), pedido.tipos_permitidos, uso)


# --------------------------------------------------------------------------
# Adaptador simulado
# --------------------------------------------------------------------------

@dataclass
class AdaptadorSimulado:
    """Prova o RF-04: o pipeline funciona com este no lugar do concreto.

    Não é código de teste escondido em produção — é a demonstração executável
    de que a fronteira é real. Se algum dia trocar este adaptador exigir mexer
    em outro arquivo, a fronteira vazou e o teste T016 falha.
    """

    resposta: Callable[[PedidoClassificacao], dict] | None = None
    nome: str = "simulado"

    def classificar(self, pedido: PedidoClassificacao) -> Classificacao:
        if self.resposta is not None:
            dados = self.resposta(pedido)
        else:
            dados = {
                "assunto": pedido.texto_bruto.strip()[:60] or "registro sem assunto",
                "tipo": pedido.tipos_permitidos[0],
                "proximos_passos": ["Revisar este registro"],
                "multiplos_temas": False,
            }
        return validar(dados, pedido.tipos_permitidos, Uso(provedor=self.nome))


registrar("anthropic", lambda **o: AdaptadorAnthropic(**o))
registrar("simulado", lambda **o: AdaptadorSimulado())
