"""T031 — validação da resposta.

**Permanece obrigatória mesmo com a imposição de esquema do adaptador ativa.**
O esquema forçado é recurso de provedor: existe em alguns, não em outros, e a
escolha de provedor foi deliberadamente adiada. Esta camada é a garantia
portável — o piso que vale independentemente de quem responda.

A regra mais importante daqui é o conjunto fechado de tipos. Se o modelo puder
inventar categoria nova, elas proliferam e o acervo fica impossível de filtrar,
reintroduzindo pela porta dos fundos o problema de taxonomia que o projeto
inteiro existe para evitar.
"""

from __future__ import annotations

import json
import re

from .erros import RespostaInvalida
from .fronteira import Classificacao, Uso

_VERBOS_VAGOS = re.compile(
    r"^\s*(pensar|refletir|considerar|avaliar|analisar|estudar|ver)\b", re.IGNORECASE
)


def extrair_json(bruto: str) -> dict:
    """Aceita JSON puro ou JSON embrulhado em cerca de código.

    Tolerância deliberada: um modelo que devolve a resposta correta dentro de
    ```json não errou de forma que valha uma nova tentativa paga.
    """
    texto = bruto.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.MULTILINE).strip()
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise RespostaInvalida(f"resposta não é JSON válido: {erro}") from erro
    if not isinstance(dados, dict):
        raise RespostaInvalida("resposta JSON não é um objeto")
    return dados


def validar(
    dados: dict,
    tipos_permitidos: tuple[str, ...],
    uso: Uso | None = None,
) -> Classificacao:
    assunto = str(dados.get("assunto", "")).strip()
    if not assunto:
        raise RespostaInvalida("campo 'assunto' ausente ou vazio")

    tipo = str(dados.get("tipo", "")).strip().lower()
    permitidos = tuple(t.lower() for t in tipos_permitidos)
    if tipo not in permitidos:
        raise RespostaInvalida(
            f"tipo {tipo!r} fora do conjunto fechado {permitidos}"
        )

    passos_brutos = dados.get("proximos_passos")
    if isinstance(passos_brutos, str):
        passos_brutos = [passos_brutos]
    if not isinstance(passos_brutos, list) or not passos_brutos:
        raise RespostaInvalida("campo 'proximos_passos' ausente ou vazio")

    passos = tuple(str(p).strip() for p in passos_brutos if str(p).strip())
    if not passos:
        raise RespostaInvalida("nenhum próximo passo utilizável na resposta")

    return Classificacao(
        assunto=assunto,
        tipo=tipo,
        proximos_passos=passos,
        multiplos_temas=bool(dados.get("multiplos_temas", False)),
        uso=uso or Uso(),
    )


def passos_vagos(classificacao: Classificacao) -> tuple[str, ...]:
    """RF-11. Diagnóstico, não bloqueio.

    Um próximo passo do tipo "pensar melhor sobre isso" não é acionável e não
    pode ser marcado como executado — mas rejeitar a resposta inteira por causa
    dele seria descartar um registro por questão de estilo. Sinalizar permite
    ajustar o prompt, que é onde o problema se resolve.
    """
    return tuple(p for p in classificacao.proximos_passos if _VERBOS_VAGOS.match(p))
