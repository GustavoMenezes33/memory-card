"""T035 — a entidade `ItemFila`.

Componente **sem spec** em `_reversa_sdd/sdd/` — é o risco R-06 do roadmap.
Ele emergiu do plano, não das specs, e existe por dois motivos que nenhum outro
componente cobre: sustentar o processamento exatamente-uma-vez através de
reinícios, e proteger a máquina pessoal do usuário durante rajadas.

Rodar `/reversa-sync` depois da entrega para convergir isto na extração, senão
a documentação nasce desatualizada.

O campo `etapa` é a peça central: é ele que permite retomar do ponto correto
depois de uma queda, sem repetir a transcrição de um áudio já transcrito — o
que torna exatamente-uma-vez implementável sem transação.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class Etapa(str, Enum):
    """Ordem fixa. Retomar significa continuar da etapa registrada."""
    RECEBIDO = "recebido"
    BAIXADO = "baixado"
    TRANSCRITO = "transcrito"
    CLASSIFICADO = "classificado"
    ARQUIVADO = "arquivado"
    FALHOU = "falhou"


_ORDEM = (
    Etapa.RECEBIDO,
    Etapa.BAIXADO,
    Etapa.TRANSCRITO,
    Etapa.CLASSIFICADO,
    Etapa.ARQUIVADO,
)


def proxima_etapa(atual: Etapa) -> Etapa | None:
    if atual in (Etapa.ARQUIVADO, Etapa.FALHOU):
        return None
    return _ORDEM[_ORDEM.index(atual) + 1]


@dataclass(frozen=True)
class ItemFila:
    id: str
    telegram_message_id: int
    telegram_chat_id: int
    tipo_origem: str = "voz"
    etapa: Etapa = Etapa.RECEBIDO
    audio_path: str = ""
    texto_bruto: str = ""
    duracao_segundos: float | None = None
    registro_id: str = ""
    tentativas: int = 0
    ultimo_erro: str = ""
    enfileirado_em: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def concluido(self) -> bool:
        return self.etapa in (Etapa.ARQUIVADO, Etapa.FALHOU)

    def avancar(self, **campos) -> "ItemFila":
        seguinte = proxima_etapa(self.etapa)
        if seguinte is None:
            return self
        return replace(self, etapa=seguinte, **campos)

    def falhar(self, motivo: str) -> "ItemFila":
        return replace(
            self, etapa=Etapa.FALHOU, ultimo_erro=motivo, tentativas=self.tentativas + 1
        )


def caminho_do_item(pasta: Path, identificador: str) -> Path:
    return pasta / f"{identificador}.json"


def salvar(pasta: Path, item: ItemFila) -> Path:
    """Escrita atômica: um item pela metade seria pior que item nenhum."""
    import os
    import tempfile

    pasta.mkdir(parents=True, exist_ok=True)
    dados = asdict(item)
    dados["etapa"] = item.etapa.value

    destino = caminho_do_item(pasta, item.id)
    descritor, temporario = tempfile.mkstemp(dir=str(pasta), prefix=".tmp-", suffix=".json")
    with os.fdopen(descritor, "w", encoding="utf-8", newline="\n") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2, sort_keys=True)
        arquivo.flush()
        os.fsync(arquivo.fileno())
    os.replace(temporario, destino)
    return destino


def carregar(caminho: Path) -> ItemFila:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados["etapa"] = Etapa(dados.get("etapa", Etapa.RECEBIDO.value))
    return ItemFila(**dados)


def listar_pendentes(pasta: Path) -> list[ItemFila]:
    """Ordem de chegada. Uma rajada é processada na sequência em que ocorreu."""
    if not pasta.exists():
        return []
    itens: list[ItemFila] = []
    for caminho in sorted(pasta.glob("*.json")):
        try:
            item = carregar(caminho)
        except (json.JSONDecodeError, TypeError, ValueError, OSError):
            continue
        if not item.concluido:
            itens.append(item)
    itens.sort(key=lambda i: i.enfileirado_em)
    return itens
