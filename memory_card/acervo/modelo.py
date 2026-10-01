"""T019 — a entidade `Registro`.

É o único ativo do sistema com valor duradouro. Tudo o mais (fila, índice,
estado de polling) é operacional e descartável.

Duas propriedades que o resto do código precisa respeitar:

- `texto_bruto` é **imutável**. Nenhum componente o sobrescreve, nunca. É o que
  permite reclassificar o acervo inteiro sem reprocessar áudio quando o critério
  de classificação melhorar.
- `id` é **estável e independente do caminho**. Mover ou renomear o arquivo não
  altera o identificador, porque ele vive nos metadados e não no nome.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum


class Origem(str, Enum):
    VOZ = "voz"
    TEXTO = "texto"
    REUNIAO = "reuniao"          # valor novo nesta feature


class Estado(str, Enum):
    PENDENTE = "pendente"
    EXECUTADO = "executado"
    DESCARTADO = "descartado"


# Ordem canônica dos campos no cabeçalho. Fixa, para que dois registros
# equivalentes produzam bytes equivalentes e o diff de um acervo versionado
# mostre só o que mudou de verdade.
CAMPOS_CABECALHO = (
    "id",
    "capturado_em",
    "origem",
    "contem_terceiros",
    "assunto",
    "tipo",
    "proximos_passos",
    "estado",
    "estado_alterado_em",
    "classificado",
    "motivo_nao_classificado",
    "audio_path",
    "duracao_segundos",
)


@dataclass(frozen=True)
class Registro:
    id: str
    capturado_em: datetime
    origem: Origem
    texto_bruto: str

    assunto: str = ""
    tipo: str = ""
    proximos_passos: tuple[str, ...] = field(default=())
    estado: Estado = Estado.PENDENTE
    estado_alterado_em: datetime | None = None
    classificado: bool = False
    motivo_nao_classificado: str = ""
    audio_path: str = ""
    duracao_segundos: float | None = None

    @property
    def contem_terceiros(self) -> bool:
        """RN-09. Reunião contém fala de outras pessoas; nota de voz, não.

        Derivado em vez de armazenado: não há como os dois divergirem.
        """
        return self.origem is Origem.REUNIAO

    def com_estado(self, novo: Estado, quando: datetime | None = None) -> "Registro":
        """Devolve uma cópia com o estado alterado. Não muta nada.

        Só o estado e a data da mudança se alteram — o texto bruto e os demais
        metadados são copiados intactos, o que é a garantia do RF-06.
        """
        return replace(
            self,
            estado=novo,
            estado_alterado_em=quando or datetime.now(timezone.utc),
        )


# --------------------------------------------------------------------------
# Serialização do cabeçalho
# --------------------------------------------------------------------------

def _valor_para_texto(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, datetime):
        return valor.astimezone(timezone.utc).isoformat(timespec="seconds")
    if isinstance(valor, Enum):
        return str(valor.value)
    return str(valor)


def cabecalho_para_linhas(reg: Registro) -> list[str]:
    """Cabeçalho em formato chave: valor, com listas em linhas `  - item`.

    Formato escolhido para ser legível por humano sem nenhuma ferramenta — que
    é o requisito de portabilidade — e trivialmente reversível por `leitura.py`.
    """
    linhas: list[str] = []
    for campo in CAMPOS_CABECALHO:
        valor = getattr(reg, campo)
        if campo == "proximos_passos":
            linhas.append("proximos_passos:")
            for passo in valor:
                # JSON para o item: preserva dois-pontos, quebras e acentos
                # sem inventar regra de escape própria.
                linhas.append(f"  - {json.dumps(passo, ensure_ascii=False)}")
            continue
        linhas.append(f"{campo}: {_valor_para_texto(valor)}")
    return linhas


def para_markdown(reg: Registro) -> str:
    """Arquivo completo: cabeçalho entre marcadores, depois o texto bruto."""
    partes = ["---", *cabecalho_para_linhas(reg), "---", ""]
    if reg.assunto:
        partes += [f"# {reg.assunto}", ""]
    partes += ["## Texto bruto", "", reg.texto_bruto.strip(), ""]
    return "\n".join(partes)
