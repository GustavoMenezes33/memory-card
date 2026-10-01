"""T044 — a esteira, do Telegram ao arquivo.

Liga captura, fila, transcrição, classificação e arquivamento. É aqui que a
regra mais importante do produto vira código:

**Falha de classificação nunca impede o arquivamento.**

Perder o insight é inaceitável; perder a estrutura é recuperável, porque o texto
bruto permanece íntegro e permite reclassificar depois. Por isso a etapa de
classificação captura o erro, registra o motivo e deixa a esteira seguir — em vez
de propagar e derrubar o item.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .acervo import caminhos as C
from .acervo.escrita import gravar_registro
from .acervo.modelo import Origem, Registro
from .captura import respostas as R
from .captura.download import baixar_audio, extrair_audio
from .captura.polling import ClienteTelegram
from .classificacao import custo
from .classificacao import duas_passagens as DP
from .classificacao.erros import ErroDeClassificacao
from .classificacao.fronteira import Adaptador, PedidoClassificacao
from .classificacao.validacao import passos_vagos
from .config import Config
from .fila.maquina import Maquina
from .fila.modelo import Etapa, ItemFila
from .log import obter, registrar
from .transcricao import politica as P
from .transcricao.whisper_local import ErroDeTranscricao, transcrever

_log = obter("esteira")


@dataclass
class Esteira:
    cfg: Config
    cliente: ClienteTelegram
    adaptador: Adaptador
    conversas: dict[str, R.Conversa]

    # ---------------------------------------------------------------- etapas

    def baixar(self, item: ItemFila) -> dict:
        if item.tipo_origem == "texto":
            return {}
        destino = self.cfg.captura_pasta_audio / f"{item.id}.ogg"
        baixar_audio(
            self.cliente,
            item.audio_path,          # aqui ainda é o file_id remoto
            destino,
            tentativas=self.cfg.captura_tentativas_download,
            timeout_s=self.cfg.captura_timeout_download_s,
        )
        return {"audio_path": str(destino)}

    def transcrever(self, item: ItemFila) -> dict:
        if item.texto_bruto:
            return {}   # veio como texto: nada a transcrever

        politica = P.decidir(
            item.duracao_segundos,
            self.cfg.audio_longo_limite_s,
            self.cfg.whisper_timeout_s,
            self.cfg.whisper_timeout_longo_s,
        )
        resultado = transcrever(
            Path(item.audio_path),
            modelo=self.cfg.whisper_modelo,
            idioma=self.cfg.whisper_idioma,
            dispositivo=self.cfg.whisper_dispositivo,
            pasta_modelos=self.cfg.whisper_pasta_modelos,
            timeout_s=politica.timeout_s,
        )
        registrar(
            _log,
            logging.INFO,
            "transcrição concluída",
            item=item.id,
            duracao_s=resultado.duracao_segundos,
            processamento_s=resultado.tempo_processamento_s,
            modelo=resultado.modelo_utilizado,
            vazia=resultado.vazia,
        )
        return {
            "texto_bruto": resultado.texto_bruto,
            "duracao_segundos": resultado.duracao_segundos,
        }

    def classificar(self, item: ItemFila) -> dict:
        """Nunca propaga erro: o registro precisa ser arquivado de qualquer jeito."""
        if not item.texto_bruto.strip():
            # EC-04: silêncio no bolso. Nenhuma chamada à API, custo zero.
            return {"registro_id": "", "ultimo_erro": "sem conteúdo"}

        politica = P.decidir(
            item.duracao_segundos,
            self.cfg.audio_longo_limite_s,
            self.cfg.whisper_timeout_s,
            self.cfg.whisper_timeout_longo_s,
        )
        pedido = PedidoClassificacao(
            texto_bruto=item.texto_bruto,
            tipos_permitidos=self.cfg.llm_tipos_registro,
            prompt=self._prompt(),
            modelo=self.cfg.llm_modelo,
            timeout_s=self.cfg.llm_timeout_s,
            multiplos_passos=politica.e_longo,
        )

        try:
            if politica.e_longo:
                resultado = DP.classificar_longo(self.adaptador, pedido)
            else:
                resultado = self.adaptador.classificar(pedido)
        except ErroDeClassificacao as erro:
            registrar(
                _log,
                logging.WARNING,
                "classificação falhou, arquivando sem estrutura",
                item=item.id,
                motivo=erro.motivo,
            )
            return {"ultimo_erro": f"{erro.motivo}: {erro}"}

        # T034 e T056: o custo é anotado a cada chamada, para o painel somar por
        # período. O usuário não definiu teto — sem registro, a conta surpreende
        # exatamente quando o sistema está dando certo.
        custo.anotar(
            self.arquivo_de_custos,
            resultado.uso,
            registro_id=item.id,
            perfil_audio=politica.perfil.value,
            passagens=2 if politica.e_longo else 1,
        )

        vagos = passos_vagos(resultado)
        if vagos:
            # RF-11: diagnóstico, não bloqueio. Um próximo passo do tipo "pensar
            # melhor" não é acionável e não pode ser marcado como executado —
            # mas rejeitar o registro por isso seria descartá-lo por estilo.
            registrar(
                _log,
                logging.INFO,
                "próximo passo vago sugerido pelo modelo",
                item=item.id,
                passos=list(vagos),
            )

        self._classificacoes[item.id] = resultado
        return {}

    def arquivar(self, item: ItemFila) -> dict:
        classificacao = self._classificacoes.pop(item.id, None)
        quando = datetime.now(timezone.utc)

        origem = {
            "texto": Origem.TEXTO,
            "reuniao": Origem.REUNIAO,
        }.get(item.tipo_origem, Origem.VOZ)

        registro_id = C.gerar_id(quando)
        registro = Registro(
            id=registro_id,
            capturado_em=quando,
            origem=origem,
            texto_bruto=item.texto_bruto,
            assunto=classificacao.assunto if classificacao else "",
            tipo=classificacao.tipo if classificacao else "",
            proximos_passos=classificacao.proximos_passos if classificacao else (),
            classificado=classificacao is not None,
            motivo_nao_classificado="" if classificacao else (item.ultimo_erro or "sem conteúdo"),
            audio_path=item.audio_path,
            duracao_segundos=item.duracao_segundos,
        )

        destino = C.caminho_do_registro(
            self.cfg.acervo_pasta,
            registro_id,
            registro.assunto or "sem assunto",
            quando,
            self.cfg.acervo_granularidade_pasta,
            self.cfg.acervo_tamanho_max_nome,
        )
        gravar_registro(destino, registro)

        conversa = self.conversas.get(item.id)
        if conversa:
            if classificacao:
                conversa.finalizar(
                    R.confirmacao(registro.assunto, registro.proximos_passos)
                )
            else:
                conversa.finalizar(
                    R.confirmacao_sem_classificacao(registro.motivo_nao_classificado)
                )
        return {"registro_id": registro_id}

    # ---------------------------------------------------------------- apoio

    _classificacoes: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._classificacoes = {}

    @property
    def arquivo_de_custos(self) -> Path:
        """Derivado da pasta de dados, sem novo parâmetro de configuração.

        O `.env` já tem 39 entradas; acrescentar uma quadragésima para um
        arquivo que o usuário nunca vai querer mover é custo sem benefício.
        """
        return self.cfg.acervo_indice_arquivo.parent / "custos.jsonl"

    def _prompt(self) -> str:
        try:
            return self.cfg.llm_prompt_arquivo.read_text(encoding="utf-8")
        except OSError:
            registrar(_log, logging.ERROR, "prompt não encontrado, usando fallback")
            return (
                "Extraia da transcrição um assunto curto, um tipo de registro e "
                "uma lista de próximos passos concretos. Responda em JSON."
            )

    def montar_maquina(self, pasta_fila: Path) -> Maquina:
        return Maquina(
            pasta_fila,
            {
                Etapa.RECEBIDO: self.baixar,
                Etapa.BAIXADO: self.transcrever,
                Etapa.TRANSCRITO: self.classificar,
                Etapa.CLASSIFICADO: self.arquivar,
            },
        )


def item_de_mensagem(identificador: str, mensagem: dict) -> ItemFila | None:
    """Traduz a mensagem do Telegram em item de fila. `None` se não for capturável."""
    from .captura.texto import extrair_texto, item_de_texto

    texto = extrair_texto(mensagem)
    if texto:
        return item_de_texto(identificador, mensagem, texto)

    audio = extrair_audio(mensagem)
    if audio is None:
        return None

    file_id, duracao = audio
    return ItemFila(
        id=identificador,
        telegram_message_id=int(mensagem.get("message_id", 0)),
        telegram_chat_id=int((mensagem.get("chat") or {}).get("id", 0)),
        tipo_origem="voz",
        audio_path=file_id,          # substituído pelo caminho local no download
        duracao_segundos=duracao,
    )
