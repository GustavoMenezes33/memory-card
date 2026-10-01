"""T054 — o processo único.

Decisão D-01 do roadmap: um processo hospeda o consumidor do Telegram, o
servidor do painel e o agendador do digest. Usuário único, máquina única, sem
requisito de escala — um comando sobe tudo e não há orquestração a manter. O
custo de separar seria pago todo dia sem contrapartida.

A ordem de inicialização não é arbitrária: **a configuração é validada antes de
qualquer coisa subir.** Um `.env` incompleto ou uma interface de rede errada
derrubam o processo aqui, antes de o painel existir e antes de a primeira
mensagem ser lida.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from datetime import datetime, timezone

from . import config as C
from . import log as L
from .acervo import indice as IDX
from .captura import respostas as R
from .captura.autorizacao import autorizado
from .captura.polling import ClienteTelegram, EstadoPolling, TokenInvalido, extrair_mensagens
from .captura.texto import e_comando, extrair_texto
from .classificacao import adaptador as _adaptadores  # noqa: F401 — registra os adaptadores
from .classificacao.fronteira import obter_adaptador
from .digest import montagem, selecao
from .digest.agendador import Agendador, RegistroDeEnvios
from .digest.envio import Credenciais, ErroDeEnvio, enviar
from .esteira import Esteira, item_de_mensagem
from .fila.executor import ExecutorSerial
from .painel import servidor
from .transcricao import politica as P

_log = L.obter("app")


# --------------------------------------------------------------------------
# Laço de captura
# --------------------------------------------------------------------------

def laco_de_captura(cfg: C.Config, esteira: Esteira, executor: ExecutorSerial) -> None:
    cliente = esteira.cliente
    estado = EstadoPolling.carregar(cfg.captura_estado_polling)

    # Pendentes de uma execução anterior primeiro: uma rajada interrompida
    # continua de onde parou antes de aceitar trabalho novo.
    pendentes = executor.drenar()
    if pendentes:
        L.registrar(_log, logging.INFO, "pendentes retomados", quantidade=len(pendentes))

    while True:
        try:
            atualizacoes = cliente.obter_atualizacoes(estado.ultimo_update_id + 1)
        except TokenInvalido:
            raise
        except (ConnectionError, TimeoutError) as erro:
            L.registrar(_log, logging.WARNING, "falha no polling", erro=str(erro))
            time.sleep(5)
            continue

        for update_id, mensagem in extrair_mensagens(atualizacoes):
            try:
                processar(cfg, esteira, executor, mensagem)
            except Exception as erro:  # nenhuma mensagem derruba o laço
                L.registrar(
                    _log, logging.ERROR, "falha ao processar mensagem", erro=str(erro)
                )
            # O deslocamento só avança depois do processamento: avançar antes
            # trocaria duplicata por perda.
            estado.salvar(update_id)


def processar(
    cfg: C.Config, esteira: Esteira, executor: ExecutorSerial, mensagem: dict
) -> None:
    if not autorizado(mensagem, cfg.telegram_usuario_autorizado):
        return   # descarte silencioso, já registrado em log

    chat_id = int((mensagem.get("chat") or {}).get("id", 0))
    identificador = f"{chat_id}-{mensagem.get('message_id')}"

    # Comando não entra na esteira: nenhuma fila, nenhuma chamada de API,
    # nenhum registro. Só a resposta que explica isso.
    texto = extrair_texto(mensagem)
    if e_comando(texto):
        R.Conversa(esteira.cliente, chat_id).finalizar(R.resposta_a_comando(texto or ""))
        return

    item = item_de_mensagem(identificador, mensagem)

    conversa = R.Conversa(esteira.cliente, chat_id)
    esteira.conversas[identificador] = conversa

    if item is None:
        conversa.finalizar(R.tipo_nao_suportado())
        return

    politica = P.decidir(
        item.duracao_segundos,
        cfg.audio_longo_limite_s,
        cfg.whisper_timeout_s,
        cfg.whisper_timeout_longo_s,
    )
    conversa.avisar(
        R.aviso_processamento_estendido(item.duracao_segundos)
        if politica.avisar_processamento_estendido
        else R.aviso_recebimento()
    )

    final = executor.processar_um(executor.enfileirar(item))

    # Rede de segurança da regra "exatamente uma resposta final": se a esteira
    # falhou antes de chegar ao arquivamento, ninguém respondeu ainda.
    if not conversa.respondida:
        conversa.finalizar(R.erro("processamento", final.ultimo_erro or "erro desconhecido"))
    esteira.conversas.pop(identificador, None)


# --------------------------------------------------------------------------
# Laço do digest
# --------------------------------------------------------------------------

def laco_do_digest(cfg: C.Config, intervalo_s: int = 60) -> None:
    agendador = Agendador(
        RegistroDeEnvios(cfg.acervo_indice_arquivo.parent / "ultimo_digest.json"),
        cfg.digest_dia_semana,
        *cfg.digest_horario,
    )

    while True:
        try:
            if agendador.pendente():
                despachar_digest(cfg, agendador)
        except Exception as erro:
            L.registrar(_log, logging.ERROR, "falha no laço do digest", erro=str(erro))
        time.sleep(intervalo_s)


def despachar_digest(cfg: C.Config, agendador: Agendador) -> None:
    entradas = IDX.carregar(cfg.acervo_indice_arquivo, cfg.acervo_pasta)
    escolhidos = selecao.selecionar(entradas, cfg.digest_quantidade)
    agora = datetime.now(timezone.utc)

    credenciais = Credenciais(
        servidor=cfg.smtp_servidor,
        porta=cfg.smtp_porta,
        usuario=cfg.smtp_usuario,
        senha=cfg.smtp_senha,
        remetente=cfg.digest_email_remetente,
        destino=cfg.digest_email_destino,
    )

    try:
        enviar(
            credenciais,
            montagem.assunto_do_email(escolhidos, agora),
            montagem.corpo_texto(escolhidos, cfg.painel_url_base),
            montagem.corpo_html(escolhidos, cfg.painel_url_base),
        )
    except ErroDeEnvio as erro:
        # Falha não é anotada como envio: a semana continua pendente e o
        # digest sai na execução seguinte, uma única vez.
        L.registrar(_log, logging.WARNING, "digest não enviado", motivo=erro.motivo)
        return

    agendador.concluir(
        [e.id for e in escolhidos.incluidos],
        "vazio" if escolhidos.vazia else "enviado",
        agora,
    )
    L.registrar(
        _log,
        logging.INFO,
        "digest enviado",
        quantidade=len(escolhidos.incluidos),
        pendentes=escolhidos.total_pendentes,
    )


# --------------------------------------------------------------------------
# Ponto de entrada
# --------------------------------------------------------------------------

def main() -> int:
    try:
        cfg = C.carregar()
    except C.ConfiguracaoInvalida as erro:
        print(f"Configuração inválida:\n  {erro}", file=sys.stderr)
        return 2

    L.configurar(cfg.log_nivel)
    criados = C.garantir_diretorios(cfg)
    if criados:
        L.registrar(_log, logging.INFO, "pastas criadas", pastas=[str(c) for c in criados])

    try:
        servidor.validar_interface_loopback(cfg.painel_interface)
        servidor.verificar_porta_livre(cfg.painel_interface, cfg.painel_porta)
    except (C.ConfiguracaoInvalida, servidor.PortaOcupada) as erro:
        print(f"Painel não pode iniciar:\n  {erro}", file=sys.stderr)
        return 2

    cliente = ClienteTelegram(cfg.telegram_bot_token)
    adaptador = obter_adaptador(
        cfg.llm_provedor, api_key=cfg.llm_api_key, endpoint=cfg.llm_endpoint
    )
    esteira = Esteira(cfg, cliente, adaptador, conversas={})
    executor = ExecutorSerial(cfg.fila_pasta, esteira.montar_maquina(cfg.fila_pasta))

    servidor.anunciar(cfg)
    app = servidor.criar_app(cfg)

    threading.Thread(
        target=app.run,
        kwargs={"host": cfg.painel_interface, "port": cfg.painel_porta, "debug": False},
        daemon=True,
    ).start()
    threading.Thread(target=laco_do_digest, args=(cfg,), daemon=True).start()

    try:
        laco_de_captura(cfg, esteira, executor)
    except KeyboardInterrupt:
        L.registrar(_log, logging.INFO, "encerrado pelo usuário")
        return 0
    except TokenInvalido as erro:
        print(f"Token do Telegram inválido:\n  {erro}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
