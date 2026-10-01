# Memory Card — imagem de produção
#
# Um processo só (Telegram + painel + digest), como no uso local. O estado
# inteiro vive em /app/dados, montado como volume; nada do acervo entra na
# imagem. Os segredos chegam por variável de ambiente (env_file no compose).

FROM python:3.12-slim

# tzdata: o agendador do digest usa o fuso local do processo. Sem isso,
# "sexta 19:00" seria interpretado em UTC.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=America/Sao_Paulo \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Usuário sem privilégios. O UID precisa bater com o dono de ./dados no host.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Dependências primeiro, para aproveitar o cache de camadas entre builds.
COPY pyproject.toml ./
COPY memory_card/ ./memory_card/
RUN pip install .

# Os caminhos do .env são relativos (./dados, ./config): WORKDIR é a raiz.
COPY config/ ./config/
RUN mkdir -p /app/dados && chown -R app:app /app/dados

USER app

VOLUME ["/app/dados"]

# SIGINT em vez de SIGTERM: o processo trata KeyboardInterrupt e encerra
# limpo; a fila em dados/fila retoma o que estiver pela metade.
STOPSIGNAL SIGINT

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PAINEL_PORTA', '8000') + '/', timeout=5)" || exit 1

CMD ["memory-card"]
