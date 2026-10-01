"""T041 e T043 — o que o bot responde no chat.

Este arquivo é a defesa contra o modo de falha mais grave do produto: **um
registro perdido que aparenta ter sido guardado.**

Regras que valem para toda mensagem daqui:

- Toda captura aceita recebe **exatamente uma** resposta final: confirmação ou
  erro. Nunca nenhuma, nunca as duas.
- Todo erro **nomeia a etapa** que falhou e diz que o material original foi
  preservado. "Deu erro" obriga o usuário a caçar, e caçar é o que faz alguém
  parar de confiar no sistema.
- Áudio longo recebe aviso **antes** do processamento. Sem ele, o silêncio
  durante uma transcrição de reunião é indistinguível de falha.
"""

from __future__ import annotations

from .polling import ClienteTelegram

ETAPAS = {
    "download": "baixar o áudio",
    "transcricao": "transcrever o áudio",
    "classificacao": "classificar o registro",
    "arquivamento": "gravar no acervo",
}


def aviso_recebimento() -> str:
    return "Recebido. Processando…"


def aviso_processamento_estendido(duracao_segundos: float | None) -> str:
    """RF-23. O usuário precisa saber que a espera é esperada."""
    if duracao_segundos:
        minutos = max(1, round(duracao_segundos / 60))
        return (
            f"Recebido, áudio de cerca de {minutos} min. "
            "O processamento vai levar mais tempo que o habitual; "
            "aviso aqui quando terminar."
        )
    return (
        "Recebido, áudio longo. O processamento vai levar mais tempo que o "
        "habitual; aviso aqui quando terminar."
    )


def confirmacao(assunto: str, proximos_passos: tuple[str, ...] = ()) -> str:
    linhas = [f"✅ Capturado: {assunto}"]
    if proximos_passos:
        linhas.append("")
        linhas.append("Próximo passo:" if len(proximos_passos) == 1 else "Próximos passos:")
        linhas += [f"• {p}" for p in proximos_passos]
    return "\n".join(linhas)


def confirmacao_sem_classificacao(motivo: str) -> str:
    """Registro salvo, estrutura não. A hierarquia do produto, dita ao usuário."""
    return (
        "✅ Capturado, mas sem classificação.\n"
        f"Motivo: {motivo}\n"
        "O texto foi preservado íntegro e pode ser reclassificado depois."
    )


def erro(etapa: str, detalhe: str) -> str:
    descricao = ETAPAS.get(etapa, etapa)
    return (
        f"⚠️ Falhou ao {descricao}.\n"
        f"Detalhe: {detalhe}\n"
        "O material original foi preservado e pode ser reprocessado."
    )


def resposta_a_comando(texto: str) -> str:
    """Comando não vira registro, e o usuário precisa saber disso na hora.

    Silêncio aqui seria pior que o registro-lixo que esta resposta evita: o
    usuário manda `/start`, não recebe nada e conclui que o bot está fora do ar.
    """
    comando = texto.strip().split()[0].split("@")[0].lower()
    if comando == "/start":
        return (
            "Pronto para capturar.\n"
            "Mande uma mensagem de voz ou um texto: eu transcrevo, classifico e "
            "arquivo no acervo da sua máquina.\n"
            "Comandos como este não viram registro."
        )
    return (
        "Não tenho comandos. Mande voz ou texto para capturar — "
        "comandos não viram registro."
    )


def tipo_nao_suportado() -> str:
    return (
        "Só consigo processar mensagem de voz ou texto. "
        "Este tipo de mídia não foi capturado."
    )


class Conversa:
    """Garante a regra de exatamente uma resposta final por mensagem."""

    def __init__(self, cliente: ClienteTelegram, chat_id: int) -> None:
        self._cliente = cliente
        self._chat_id = chat_id
        self._finalizada = False

    def avisar(self, texto: str) -> None:
        """Aviso intermediário. Não conta como resposta final."""
        self._cliente.enviar_mensagem(self._chat_id, texto)

    def finalizar(self, texto: str) -> None:
        if self._finalizada:
            return
        self._finalizada = True
        self._cliente.enviar_mensagem(self._chat_id, texto)

    @property
    def respondida(self) -> bool:
        return self._finalizada
