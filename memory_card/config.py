"""Carga e validação da configuração.

Todos os parâmetros vêm de `.env`. Nenhum valor de operação ou segredo
pode estar embutido em código.

Três garantias que este módulo precisa entregar, nesta ordem de importância:

1. Ausência de parâmetro obrigatório IMPEDE a inicialização, nomeando o
   parâmetro. Nunca existe modo permissivo por omissão. Vale sobretudo para
   TELEGRAM_USUARIO_AUTORIZADO: campo vazio jamais pode significar
   "aceitar qualquer remetente".
2. PAINEL_INTERFACE fora de loopback impede a inicialização. O acervo é o
   dado mais sensível do sistema e a proteção vem de não estar exposto.
3. Divergência entre PAINEL_URL_BASE e o par interface/porta é ALERTADA.
   Sem isso, o digest chega íntegro com todos os links quebrados, que é
   exatamente a falha silenciosa que este produto existe para evitar.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# T005: os oito obrigatórios declarados em um único lugar.
OBRIGATORIOS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_USUARIO_AUTORIZADO",
    "LLM_API_KEY",
    "LLM_PROVEDOR",
    "LLM_MODELO",
    "DIGEST_EMAIL_DESTINO",
    "DIGEST_EMAIL_REMETENTE",
    "SMTP_SERVIDOR",
)

DIAS_SEMANA = {
    "segunda": 0,
    "terca": 1,
    "terça": 1,
    "quarta": 2,
    "quinta": 3,
    "sexta": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}


class ConfiguracaoInvalida(Exception):
    """Erro de configuração que impede a inicialização.

    Sempre nomeia o parâmetro responsável: um erro que não diz qual campo
    está errado obriga o usuário a caçar, e caçar é o que faz alguém
    desistir de configurar direito.
    """


@dataclass(frozen=True)
class Config:
    # Captura
    telegram_bot_token: str
    telegram_usuario_autorizado: int
    captura_pasta_audio: Path
    captura_estado_polling: Path
    captura_tentativas_download: int
    captura_timeout_download_s: int

    # Transcrição
    whisper_modelo: str
    whisper_idioma: str
    whisper_dispositivo: str
    whisper_timeout_s: int
    whisper_timeout_longo_s: int
    whisper_pasta_modelos: Path
    audio_longo_limite_s: int

    # Classificação
    llm_api_key: str
    llm_provedor: str
    llm_modelo: str
    llm_endpoint: str
    llm_timeout_s: int
    llm_tentativas: int
    llm_prompt_arquivo: Path
    llm_tipos_registro: tuple[str, ...]

    # Acervo
    acervo_pasta: Path
    acervo_granularidade_pasta: str
    acervo_indice_arquivo: Path
    acervo_pasta_descartados: Path | None
    acervo_tamanho_max_nome: int

    # Digest
    digest_email_destino: str
    digest_email_remetente: str
    smtp_servidor: str
    smtp_porta: int
    smtp_usuario: str
    smtp_senha: str
    digest_dia_semana: int
    digest_horario: tuple[int, int]
    digest_quantidade: int
    painel_url_base: str

    # Painel
    painel_porta: int
    painel_interface: str
    painel_periodo_padrao: str
    painel_exibir_descartados: bool
    painel_itens_por_pagina: int

    # Operação
    fila_pasta: Path
    log_nivel: str

    # Preenchido por validar_coerencia_painel(). Não impede a inicialização.
    alertas: tuple[str, ...] = field(default=())


# --------------------------------------------------------------------------
# Leitores tipados
# --------------------------------------------------------------------------

def _texto(nome: str, padrao: str = "") -> str:
    return (os.getenv(nome) or "").strip() or padrao


def _inteiro(nome: str, padrao: int) -> int:
    bruto = _texto(nome)
    if not bruto:
        return padrao
    try:
        return int(bruto)
    except ValueError as erro:
        raise ConfiguracaoInvalida(
            f"{nome} precisa ser um número inteiro, recebi {bruto!r}."
        ) from erro


def _booleano(nome: str, padrao: bool) -> bool:
    bruto = _texto(nome).lower()
    if not bruto:
        return padrao
    if bruto in {"true", "1", "sim", "yes"}:
        return True
    if bruto in {"false", "0", "nao", "não", "no"}:
        return False
    raise ConfiguracaoInvalida(
        f"{nome} precisa ser true ou false, recebi {bruto!r}."
    )


def _caminho(nome: str, padrao: str) -> Path:
    return Path(_texto(nome, padrao)).expanduser()


def _lista(nome: str, padrao: str) -> tuple[str, ...]:
    bruto = _texto(nome, padrao)
    itens = tuple(i.strip() for i in bruto.split(",") if i.strip())
    if not itens:
        raise ConfiguracaoInvalida(f"{nome} não pode ficar vazio.")
    return itens


def _dia_semana(nome: str, padrao: str) -> int:
    bruto = _texto(nome, padrao).lower()
    if bruto not in DIAS_SEMANA:
        validos = ", ".join(sorted(set(DIAS_SEMANA)))
        raise ConfiguracaoInvalida(
            f"{nome} precisa ser um dia da semana ({validos}), recebi {bruto!r}."
        )
    return DIAS_SEMANA[bruto]


def _horario(nome: str, padrao: str) -> tuple[int, int]:
    bruto = _texto(nome, padrao)
    try:
        hora, minuto = (int(p) for p in bruto.split(":", 1))
    except ValueError as erro:
        raise ConfiguracaoInvalida(
            f"{nome} precisa estar no formato HH:MM, recebi {bruto!r}."
        ) from erro
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        raise ConfiguracaoInvalida(
            f"{nome} precisa estar entre 00:00 e 23:59, recebi {bruto!r}."
        )
    return hora, minuto


# --------------------------------------------------------------------------
# Validações que impedem a inicialização
# --------------------------------------------------------------------------

def validar_obrigatorios() -> None:
    """T005. Falha nomeando TODOS os ausentes, não apenas o primeiro.

    Relatar um de cada vez obrigaria o usuário a reiniciar seis vezes para
    descobrir seis campos faltando.
    """
    ausentes = [nome for nome in OBRIGATORIOS if not _texto(nome)]
    if ausentes:
        raise ConfiguracaoInvalida(
            "Parâmetros obrigatórios ausentes no .env: "
            + ", ".join(ausentes)
            + ". Consulte .env.example. O sistema não inicia sem eles, e "
            "em nenhuma hipótese opera em modo permissivo."
        )


def validar_interface_loopback(interface: str) -> None:
    """T006. Só loopback. Qualquer outro endereço impede a inicialização."""
    try:
        endereco = ipaddress.ip_address(interface)
    except ValueError as erro:
        if interface == "localhost":
            return
        raise ConfiguracaoInvalida(
            f"PAINEL_INTERFACE precisa ser um endereço de loopback "
            f"(127.0.0.1, ::1 ou localhost), recebi {interface!r}."
        ) from erro

    if not endereco.is_loopback:
        raise ConfiguracaoInvalida(
            f"PAINEL_INTERFACE precisa ser um endereço de loopback, recebi "
            f"{interface!r}. Expor o painel publica o acervo, que é o dado "
            "mais sensível do sistema e o único que permanece local."
        )


def validar_coerencia_painel(
    url_base: str, interface: str, porta: int
) -> list[str]:
    """T007. Divergência ALERTA, não impede.

    O painel sobe e funciona; o que quebra são os links dos digests já
    enviados, que ficam gravados na caixa de e-mail do usuário. Impedir a
    inicialização seria desproporcional; deixar em silêncio seria pior.
    """
    alertas: list[str] = []
    partes = urlparse(url_base)

    if not partes.scheme or not partes.hostname:
        alertas.append(
            f"PAINEL_URL_BASE={url_base!r} não parece um endereço válido. "
            "Os links do digest podem não funcionar."
        )
        return alertas

    porta_url = partes.port or (443 if partes.scheme == "https" else 80)
    host_equivale = partes.hostname in {interface, "localhost", "127.0.0.1", "::1"}

    if porta_url != porta or not host_equivale:
        alertas.append(
            f"PAINEL_URL_BASE aponta para {partes.hostname}:{porta_url}, mas o "
            f"painel escuta em {interface}:{porta}. Os links enviados no digest "
            "vão apontar para lugar nenhum. Ajuste PAINEL_URL_BASE ou "
            "PAINEL_PORTA para que os dois coincidam."
        )
    return alertas


# --------------------------------------------------------------------------
# Diretórios
# --------------------------------------------------------------------------

def garantir_diretorios(cfg: Config) -> list[Path]:
    """T010. Cria o que falta e devolve o que foi criado, para registro.

    Só cria diretório. Nunca cria, move ou apaga arquivo do usuário.
    """
    alvos = [
        cfg.acervo_pasta,
        cfg.captura_pasta_audio,
        cfg.whisper_pasta_modelos,
        cfg.fila_pasta,
        cfg.captura_estado_polling.parent,
        cfg.acervo_indice_arquivo.parent,
    ]
    if cfg.acervo_pasta_descartados is not None:
        alvos.append(cfg.acervo_pasta_descartados)

    criados: list[Path] = []
    for alvo in alvos:
        if not alvo.exists():
            alvo.mkdir(parents=True, exist_ok=True)
            criados.append(alvo)
    return criados


# --------------------------------------------------------------------------
# Ponto de entrada
# --------------------------------------------------------------------------

def carregar(env_file: str | os.PathLike[str] | None = ".env") -> Config:
    """T004. Lê o .env, valida e devolve a configuração congelada."""
    if env_file is not None:
        load_dotenv(env_file, override=False)

    validar_obrigatorios()

    painel_interface = _texto("PAINEL_INTERFACE", "127.0.0.1")
    validar_interface_loopback(painel_interface)

    painel_porta = _inteiro("PAINEL_PORTA", 8000)
    painel_url_base = _texto("PAINEL_URL_BASE", "http://localhost:8000").rstrip("/")
    alertas = validar_coerencia_painel(painel_url_base, painel_interface, painel_porta)

    descartados_bruto = _texto("ACERVO_PASTA_DESCARTADOS")

    granularidade = _texto("ACERVO_GRANULARIDADE_PASTA", "mensal").lower()
    if granularidade not in {"mensal", "semanal"}:
        raise ConfiguracaoInvalida(
            "ACERVO_GRANULARIDADE_PASTA precisa ser mensal ou semanal, "
            f"recebi {granularidade!r}."
        )

    try:
        usuario_autorizado = int(_texto("TELEGRAM_USUARIO_AUTORIZADO"))
    except ValueError as erro:
        raise ConfiguracaoInvalida(
            "TELEGRAM_USUARIO_AUTORIZADO precisa ser o identificador numérico "
            "do usuário no Telegram."
        ) from erro

    return Config(
        telegram_bot_token=_texto("TELEGRAM_BOT_TOKEN"),
        telegram_usuario_autorizado=usuario_autorizado,
        captura_pasta_audio=_caminho("CAPTURA_PASTA_AUDIO", "./dados/audios"),
        captura_estado_polling=_caminho(
            "CAPTURA_ESTADO_POLLING", "./dados/estado_polling.json"
        ),
        captura_tentativas_download=_inteiro("CAPTURA_TENTATIVAS_DOWNLOAD", 3),
        captura_timeout_download_s=_inteiro("CAPTURA_TIMEOUT_DOWNLOAD_S", 30),
        whisper_modelo=_texto("WHISPER_MODELO", "small"),
        whisper_idioma=_texto("WHISPER_IDIOMA", "pt"),
        whisper_dispositivo=_texto("WHISPER_DISPOSITIVO", "cpu"),
        whisper_timeout_s=_inteiro("WHISPER_TIMEOUT_S", 300),
        whisper_timeout_longo_s=_inteiro("WHISPER_TIMEOUT_LONGO_S", 3600),
        whisper_pasta_modelos=_caminho("WHISPER_PASTA_MODELOS", "./dados/modelos"),
        audio_longo_limite_s=_inteiro("AUDIO_LONGO_LIMITE_S", 180),
        llm_api_key=_texto("LLM_API_KEY"),
        llm_provedor=_texto("LLM_PROVEDOR"),
        llm_modelo=_texto("LLM_MODELO"),
        llm_endpoint=_texto("LLM_ENDPOINT"),
        llm_timeout_s=_inteiro("LLM_TIMEOUT_S", 15),
        llm_tentativas=_inteiro("LLM_TENTATIVAS", 3),
        llm_prompt_arquivo=_caminho(
            "LLM_PROMPT_ARQUIVO", "./config/prompt_classificacao.txt"
        ),
        llm_tipos_registro=_lista(
            "LLM_TIPOS_REGISTRO", "ideia,insight,tarefa,referencia,duvida"
        ),
        acervo_pasta=_caminho("ACERVO_PASTA", "./dados/acervo"),
        acervo_granularidade_pasta=granularidade,
        acervo_indice_arquivo=_caminho("ACERVO_INDICE_ARQUIVO", "./dados/indice.json"),
        acervo_pasta_descartados=(
            Path(descartados_bruto).expanduser() if descartados_bruto else None
        ),
        acervo_tamanho_max_nome=_inteiro("ACERVO_TAMANHO_MAX_NOME", 80),
        digest_email_destino=_texto("DIGEST_EMAIL_DESTINO"),
        digest_email_remetente=_texto("DIGEST_EMAIL_REMETENTE"),
        smtp_servidor=_texto("SMTP_SERVIDOR"),
        smtp_porta=_inteiro("SMTP_PORTA", 587),
        smtp_usuario=_texto("SMTP_USUARIO"),
        smtp_senha=_texto("SMTP_SENHA"),
        # Sexta, não domingo: a janela de recuperação vai do horário marcado até
        # a virada da semana ISO, na meia-noite de domingo. Com domingo às 19h
        # sobram cinco horas, e uma noite fora de casa custa o digest da semana;
        # com sexta sobram mais de dois dias. Ver GUIA-DE-CONFIGURACAO, passo 9.
        digest_dia_semana=_dia_semana("DIGEST_DIA_SEMANA", "sexta"),
        digest_horario=_horario("DIGEST_HORARIO", "19:00"),
        digest_quantidade=_inteiro("DIGEST_QUANTIDADE", 5),
        painel_url_base=painel_url_base,
        painel_porta=painel_porta,
        painel_interface=painel_interface,
        painel_periodo_padrao=_texto("PAINEL_PERIODO_PADRAO", "mes-corrente"),
        painel_exibir_descartados=_booleano("PAINEL_EXIBIR_DESCARTADOS", False),
        painel_itens_por_pagina=_inteiro("PAINEL_ITENS_POR_PAGINA", 50),
        fila_pasta=_caminho("FILA_PASTA", "./dados/fila"),
        log_nivel=_texto("LOG_NIVEL", "INFO").upper(),
        alertas=tuple(alertas),
    )
