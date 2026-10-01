"""T020 — gravação atômica.

A regra que este módulo existe para garantir: **ou o arquivo existe íntegro, ou
não existe.** Nunca um arquivo pela metade.

Arquivo parcial é indistinguível de arquivo corrompido, e um acervo em que o
usuário não pode confiar deixa de ser um acervo. O custo de evitar isso é
escrever em um temporário e renomear — `os.replace` é atômico dentro do mesmo
sistema de arquivos, por isso o temporário nasce na pasta de destino e não em
`/tmp`.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .modelo import Registro, para_markdown


class EspacoInsuficiente(Exception):
    """EC-03. Erro explícito antes de escrever, nunca escrita parcial."""


def escrever_texto_atomico(destino: Path, conteudo: str) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)

    descritor, temporario = tempfile.mkstemp(
        dir=str(destino.parent), prefix=".tmp-", suffix=".md"
    )
    try:
        with os.fdopen(descritor, "w", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            # Sem o fsync, uma queda de energia logo após o rename pode deixar
            # um arquivo de tamanho zero: o nome existe, o conteúdo não chegou.
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
    except OSError as erro:
        Path(temporario).unlink(missing_ok=True)
        if getattr(erro, "errno", None) == 28:  # ENOSPC
            raise EspacoInsuficiente(
                f"Sem espaço em disco para gravar {destino}. "
                "O áudio e a transcrição foram preservados para nova tentativa."
            ) from erro
        raise
    return destino


def gravar_registro(destino: Path, registro: Registro) -> Path:
    """Serializa e grava. Retorna o caminho efetivamente escrito."""
    return escrever_texto_atomico(destino, para_markdown(registro))
