"""T052 — envio por servidor de e-mail.

Erros separados por causa, pelo mesmo motivo de sempre: "falhou ao enviar" não
diz se o problema é a senha, o destinatário ou a rede — e só o primeiro exige
ação do usuário.

Indisponibilidade do servidor **não afeta captura, transcrição, classificação
nem arquivamento**. Só a devolução semanal deixa de ocorrer, e os registros
permanecem pendentes para o envio seguinte. Nada se perde.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


class ErroDeEnvio(Exception):
    motivo = "erro"


class ServidorIndisponivel(ErroDeEnvio):
    """Transitório: tenta na execução seguinte, sem alarmar o usuário."""
    motivo = "servidor de e-mail indisponível"


class AutenticacaoRecusada(ErroDeEnvio):
    """Distinto de indisponibilidade: exige ação do usuário, não espera.

    Causa comum: senha de aplicativo revogada pelo provedor.
    """
    motivo = "autenticação de e-mail recusada"


class DestinatarioRejeitado(ErroDeEnvio):
    motivo = "destinatário rejeitado"


@dataclass(frozen=True)
class Credenciais:
    servidor: str
    porta: int
    usuario: str
    senha: str
    remetente: str
    destino: str


def montar_mensagem(
    credenciais: Credenciais, assunto: str, texto: str, html: str
) -> EmailMessage:
    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = credenciais.remetente
    mensagem["To"] = credenciais.destino   # destinatário único, por RF-06b
    mensagem.set_content(texto)
    mensagem.add_alternative(html, subtype="html")
    return mensagem


def enviar(
    credenciais: Credenciais,
    assunto: str,
    texto: str,
    html: str,
    timeout_conexao_s: int = 30,
) -> None:
    mensagem = montar_mensagem(credenciais, assunto, texto, html)

    try:
        with smtplib.SMTP(
            credenciais.servidor, credenciais.porta, timeout=timeout_conexao_s
        ) as servidor:
            servidor.starttls()
            if credenciais.usuario:
                servidor.login(credenciais.usuario, credenciais.senha)
            servidor.send_message(mensagem)
    except smtplib.SMTPAuthenticationError as erro:
        raise AutenticacaoRecusada(
            f"o servidor recusou as credenciais: {erro}. "
            "Se o provedor exige senha de aplicativo, verifique se ela ainda é válida."
        ) from erro
    except smtplib.SMTPRecipientsRefused as erro:
        raise DestinatarioRejeitado(
            f"o destinatário {credenciais.destino!r} foi rejeitado: {erro}"
        ) from erro
    except (smtplib.SMTPException, OSError) as erro:
        raise ServidorIndisponivel(
            f"não foi possível enviar pelo servidor {credenciais.servidor}: {erro}"
        ) from erro
