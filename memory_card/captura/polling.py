"""T038 — recepção por long polling.

**Toda conexão parte da máquina local.** Não existe endereço de entrada, porta
aberta nem certificado — é isso que permite o acervo ser local sem expor a
máquina, e foi o que dissolveu o trilema registrado no PRD.

A peça central é o deslocamento de leitura persistido. Ele só avança **depois**
que a mensagem foi arquivada ou marcada como falha definitiva. Avançar antes
trocaria duplicata por perda, e perda é inaceitável enquanto duplicata é apenas
incômoda.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from ..log import obter, registrar

_log = obter("captura.polling")
BASE = "https://api.telegram.org"


class TokenInvalido(Exception):
    """Falha na inicialização, nunca laço silencioso de tentativas."""


@dataclass
class EstadoPolling:
    arquivo: Path
    ultimo_update_id: int = 0

    @classmethod
    def carregar(cls, arquivo: Path) -> "EstadoPolling":
        if not arquivo.exists():
            return cls(arquivo)
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            return cls(arquivo, int(dados.get("ultimo_update_id", 0)))
        except (json.JSONDecodeError, ValueError, OSError):
            # Estado ilegível: recomeçar do zero reprocessa mensagens já vistas,
            # o que gera duplicata. Perder o insight seria pior.
            registrar(_log, logging.WARNING, "estado de polling ilegível, recomeçando")
            return cls(arquivo)

    def salvar(self, update_id: int) -> None:
        import os
        import tempfile

        self.ultimo_update_id = update_id
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        descritor, temporario = tempfile.mkstemp(dir=str(self.arquivo.parent), prefix=".tmp-")
        with os.fdopen(descritor, "w", encoding="utf-8") as saida:
            json.dump({"ultimo_update_id": update_id}, saida)
            saida.flush()
            os.fsync(saida.fileno())
        os.replace(temporario, self.arquivo)


@dataclass
class ClienteTelegram:
    token: str
    timeout_polling_s: int = 30

    def _url(self, metodo: str) -> str:
        return f"{BASE}/bot{self.token}/{metodo}"

    def _chamar(self, metodo: str, **parametros):
        import requests

        try:
            resposta = requests.post(
                self._url(metodo),
                json=parametros,
                timeout=self.timeout_polling_s + 15,
            )
        except requests.RequestException as erro:
            raise ConnectionError(f"falha de rede em {metodo}: {erro}") from erro

        if resposta.status_code in (401, 404):
            raise TokenInvalido(
                "TELEGRAM_BOT_TOKEN foi rejeitado pela API. Verifique o valor "
                "no .env; o token pode ter sido revogado ou regenerado."
            )
        if resposta.status_code == 429:
            espera = resposta.json().get("parameters", {}).get("retry_after", 5)
            raise TimeoutError(f"limite de requisições atingido, aguardar {espera}s")
        if not resposta.ok:
            raise ConnectionError(f"{metodo} respondeu {resposta.status_code}")

        corpo = resposta.json()
        if not corpo.get("ok"):
            raise ConnectionError(f"{metodo} falhou: {corpo.get('description')}")
        return corpo["result"]

    def obter_atualizacoes(self, offset: int) -> list[dict]:
        return self._chamar(
            "getUpdates",
            offset=offset,
            timeout=self.timeout_polling_s,
            allowed_updates=["message"],
        )

    def enviar_mensagem(self, chat_id: int, texto: str) -> None:
        """Falha aqui afeta a notificação, não o dado: o registro já está salvo."""
        try:
            self._chamar("sendMessage", chat_id=chat_id, text=texto)
        except Exception as erro:
            registrar(_log, logging.ERROR, "falha ao responder no chat", erro=str(erro))

    def caminho_do_arquivo(self, file_id: str) -> str:
        return self._chamar("getFile", file_id=file_id)["file_path"]

    def baixar(self, file_path: str, destino: Path, timeout_s: int) -> Path:
        import requests

        url = f"{BASE}/file/bot{self.token}/{file_path}"
        destino.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=timeout_s) as resposta:
            resposta.raise_for_status()
            with destino.open("wb") as saida:
                for bloco in resposta.iter_content(chunk_size=65536):
                    saida.write(bloco)
        return destino


def extrair_mensagens(atualizacoes: list[dict]) -> list[tuple[int, dict]]:
    """`(update_id, message)` para cada atualização que traz mensagem."""
    return [
        (a["update_id"], a["message"])
        for a in atualizacoes
        if isinstance(a.get("message"), dict)
    ]
