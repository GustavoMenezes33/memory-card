"""T037 — execução estritamente serial.

**Uma transcrição por vez.** Não é limitação técnica, é decisão de produto: a
máquina é pessoal e o usuário está usando ela para outra coisa. Paralelizar
transcrições tornaria o computador inutilizável durante uma rajada de capturas,
e o sistema existe para não atrapalhar o dia dele.

A fila é persistida em disco, então a serialização sobrevive a reinício: uma
rajada interrompida continua de onde parou, na ordem em que chegou.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from .maquina import Maquina
from .modelo import ItemFila, listar_pendentes, salvar


@dataclass
class ExecutorSerial:
    pasta: Path
    maquina: Maquina
    _trava: threading.Lock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._trava is None:
            self._trava = threading.Lock()

    def enfileirar(self, item: ItemFila) -> ItemFila:
        """Persiste antes de qualquer processamento.

        Se o processo cair entre receber e processar, o item já está em disco e
        será retomado. Enfileirar só em memória trocaria durabilidade por
        velocidade num ponto onde a velocidade não importa.
        """
        salvar(self.pasta, item)
        return item

    def processar_um(self, item: ItemFila) -> ItemFila:
        with self._trava:
            return self.maquina.executar_ate_o_fim(item)

    def drenar(self, limite: int | None = None) -> list[ItemFila]:
        """Processa os pendentes em ordem de chegada.

        Usado na retomada após o processo voltar: tudo que ficou pendente é
        processado antes de aceitar trabalho novo.
        """
        processados: list[ItemFila] = []
        for indice, item in enumerate(listar_pendentes(self.pasta)):
            if limite is not None and indice >= limite:
                break
            processados.append(self.processar_um(item))
        return processados

    def pendentes(self) -> list[ItemFila]:
        return listar_pendentes(self.pasta)
