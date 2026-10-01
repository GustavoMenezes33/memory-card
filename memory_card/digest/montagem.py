"""T051 — montagem do e-mail.

Duas exigências que parecem estéticas e são funcionais:

- **Legível com imagens bloqueadas.** Clientes de e-mail bloqueiam imagens por
  padrão, e um digest que chega vazio é indistinguível de falha. Nenhum conteúdo
  essencial pode depender de recurso remoto — por isso a versão em texto puro
  acompanha sempre.
- **O total de pendentes vai no rodapé.** É como o usuário percebe acúmulo sem
  precisar abrir o painel: cinco registros por semana com trinta pendentes conta
  uma história diferente de cinco com seis.
"""

from __future__ import annotations

from datetime import datetime

from ..acervo.indice import EntradaIndice
from ..painel.confirmacao import url_de_marcacao
from .selecao import Selecao


def _data_curta(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m")
    except ValueError:
        return iso[:10]


def assunto_do_email(selecao: Selecao, quando: datetime) -> str:
    if selecao.vazia:
        return f"Memory Card · nada pendente ({quando:%d/%m})"
    quantidade = len(selecao.incluidos)
    plural = "registro" if quantidade == 1 else "registros"
    return f"Memory Card · {quantidade} {plural} para revisitar ({quando:%d/%m})"


def corpo_texto(selecao: Selecao, url_base: str) -> str:
    if selecao.vazia:
        return (
            "Nenhum registro pendente esta semana.\n\n"
            "Esta mensagem chega mesmo sem pendências: silêncio seria "
            "indistinguível de falha, e o ritmo semanal é o que sustenta o hábito.\n"
        )

    partes: list[str] = []
    for indice, entrada in enumerate(selecao.incluidos, start=1):
        cabecalho = f"{indice}. {entrada.assunto or '(sem assunto)'}"
        if entrada.origem == "reuniao":
            cabecalho += "  [reunião — contém fala de terceiros]"
        if not entrada.classificado:
            cabecalho += "  [não classificado]"

        partes.append(cabecalho)
        partes.append(f"   capturado em {_data_curta(entrada.capturado_em)}")
        partes.append(f"   feito:     {url_de_marcacao(url_base, entrada.id, 'executado')}")
        partes.append(f"   descartar: {url_de_marcacao(url_base, entrada.id, 'descartado')}")
        partes.append("")

    partes.append(f"— {selecao.total_pendentes} registros pendentes no total.")
    if selecao.restantes:
        partes.append(f"  {selecao.restantes} ficaram para os próximos envios.")
    partes.append("")
    partes.append(
        "Os links abrem uma página de confirmação no painel local. "
        "Abrir não marca nada: só o botão de confirmar altera o registro."
    )
    return "\n".join(partes)


def corpo_html(selecao: Selecao, url_base: str, proximos_passos: dict[str, tuple[str, ...]] | None = None) -> str:
    passos_por_id = proximos_passos or {}

    if selecao.vazia:
        return (
            "<html><body style='font-family:system-ui,sans-serif;max-width:40rem'>"
            "<p>Nenhum registro pendente esta semana.</p>"
            "<p style='color:#666;font-size:.9rem'>Esta mensagem chega mesmo sem "
            "pendências: silêncio seria indistinguível de falha.</p>"
            "</body></html>"
        )

    from html import escape

    itens: list[str] = []
    for entrada in selecao.incluidos:
        marcas = ""
        if entrada.origem == "reuniao":
            marcas += " <span style='color:#38c'>· reunião</span>"
        if not entrada.classificado:
            marcas += " <span style='color:#c33'>· não classificado</span>"

        passos = passos_por_id.get(entrada.id, ())
        lista = "".join(f"<li>{escape(p)}</li>" for p in passos)
        itens.append(
            "<li style='margin:1.2rem 0'>"
            f"<b>{escape(entrada.assunto) or '(sem assunto)'}</b>{marcas}<br>"
            f"<span style='color:#666;font-size:.85rem'>capturado em "
            f"{_data_curta(entrada.capturado_em)}</span>"
            + (f"<ul>{lista}</ul>" if lista else "")
            + f"<a href='{url_de_marcacao(url_base, entrada.id, 'executado')}'>feito</a>"
            f" &nbsp;·&nbsp; "
            f"<a href='{url_de_marcacao(url_base, entrada.id, 'descartado')}'>descartar</a>"
            "</li>"
        )

    return (
        "<html><body style='font-family:system-ui,sans-serif;max-width:40rem'>"
        f"<ul style='list-style:none;padding:0'>{''.join(itens)}</ul>"
        f"<p style='color:#666;font-size:.85rem'>{selecao.total_pendentes} registros "
        f"pendentes no total"
        + (f", {selecao.restantes} para os próximos envios" if selecao.restantes else "")
        + ".<br>Os links abrem uma página de confirmação no painel local; "
        "abrir não marca nada.</p></body></html>"
    )
