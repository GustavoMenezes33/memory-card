"""T026 e T028 — transcrição local.

O único componente do sistema que **não fala com ninguém**. Nenhum áudio e
nenhuma transcrição saem da máquina; a única requisição de rede possível é a
obtenção do modelo, uma vez, antes da primeira transcrição.

Duas decisões que parecem detalhe e não são:

- **Transcrição vazia é resultado válido, não erro.** Um botão acionado por
  engano no bolso não é falha do sistema. Confundir os dois geraria alarme falso
  e desgastaria a confiança em todos os avisos de erro — o dia em que houvesse
  uma falha de verdade, o usuário já teria aprendido a ignorá-la.
- **Cada modo de falha tem erro próprio e nomeado.** "Falhou ao transcrever" não
  diz se o problema é o arquivo, o modelo ou a máquina, e essa distinção é a
  diferença entre corrigir em um minuto e caçar por uma hora.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


class ErroDeTranscricao(Exception):
    """Base. Todo erro deste módulo nomeia sua causa."""


class ArquivoCorrompido(ErroDeTranscricao):
    """EC-02. Download interrompido, arquivo truncado."""


class FormatoNaoSuportado(ErroDeTranscricao):
    """EC-03."""


class ModeloAusente(ErroDeTranscricao):
    """EC-05. Primeira execução sem rede — falha explícita, sem laço silencioso."""


class MemoriaInsuficiente(ErroDeTranscricao):
    """EC-06. Modelo grande em máquina modesta; sugere modelo menor."""


class TempoExcedido(ErroDeTranscricao):
    """EC-04. O áudio é preservado; a transcrição pode ser retomada depois."""


@dataclass(frozen=True)
class Transcricao:
    texto_bruto: str
    idioma_detectado: str
    duracao_segundos: float
    modelo_utilizado: str
    tempo_processamento_s: float
    vazia: bool


def _carregar_modelo(modelo: str, dispositivo: str, pasta_modelos: Path):
    """Importação tardia: o pacote só é exigido quando há áudio para transcrever.

    Sem isso, testar configuração exigiria ter o Whisper instalado.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as erro:  # pragma: no cover - depende do ambiente
        raise ModeloAusente(
            "faster-whisper não está instalado. Instale as dependências do "
            "projeto antes de transcrever áudio."
        ) from erro

    try:
        return WhisperModel(
            modelo,
            device=dispositivo,
            download_root=str(pasta_modelos),
            compute_type="int8" if dispositivo == "cpu" else "float16",
        )
    except MemoryError as erro:  # pragma: no cover
        raise MemoriaInsuficiente(
            f"memória insuficiente para o modelo {modelo!r}. "
            "Configure WHISPER_MODELO com um modelo menor, por exemplo 'base'."
        ) from erro
    except Exception as erro:  # pragma: no cover
        raise ModeloAusente(
            f"não foi possível carregar o modelo {modelo!r}: {erro}"
        ) from erro


def transcrever(
    audio: Path,
    modelo: str,
    idioma: str,
    dispositivo: str,
    pasta_modelos: Path,
    timeout_s: int,
) -> Transcricao:
    """Transcreve e devolve o texto bruto, que a partir daqui é imutável."""
    if not audio.exists():
        raise ArquivoCorrompido(f"arquivo de áudio não encontrado: {audio}")
    if audio.stat().st_size == 0:
        raise ArquivoCorrompido(f"arquivo de áudio vazio: {audio}")

    motor = _carregar_modelo(modelo, dispositivo, pasta_modelos)
    inicio = time.monotonic()

    try:
        segmentos, info = motor.transcribe(
            str(audio),
            language=idioma or None,   # dica, não restrição: EC-07
            vad_filter=True,
        )
    except MemoryError as erro:  # pragma: no cover
        raise MemoriaInsuficiente(
            f"memória insuficiente ao transcrever {audio.name}"
        ) from erro
    except Exception as erro:  # pragma: no cover
        mensagem = str(erro).lower()
        if "format" in mensagem or "codec" in mensagem:
            raise FormatoNaoSuportado(
                f"formato de áudio não suportado em {audio.name}: {erro}"
            ) from erro
        raise ArquivoCorrompido(
            f"não foi possível ler o áudio {audio.name}: {erro}"
        ) from erro

    # Os segmentos chegam preguiçosamente, então o limite de tempo é verificado
    # entre eles. Isso interrompe de verdade um áudio longo demais, em vez de
    # descobrir o estouro só no final.
    partes: list[str] = []
    for segmento in segmentos:
        if time.monotonic() - inicio > timeout_s:
            raise TempoExcedido(
                f"transcrição de {audio.name} excedeu {timeout_s}s. "
                "O áudio foi preservado e pode ser reprocessado."
            )
        partes.append(segmento.text)

    texto = " ".join(p.strip() for p in partes).strip()
    decorrido = time.monotonic() - inicio

    return Transcricao(
        texto_bruto=texto,
        idioma_detectado=getattr(info, "language", idioma) or "",
        duracao_segundos=float(getattr(info, "duration", 0.0)),
        modelo_utilizado=modelo,
        tempo_processamento_s=round(decorrido, 2),
        vazia=not texto,   # EC-01: sinalizado, jamais tratado como falha
    )
