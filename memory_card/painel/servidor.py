"""T045 — o servidor HTTP local.

Três regras de rede, todas com severidade deliberada:

- **Interface fora de loopback impede a inicialização.** O acervo é o dado mais
  sensível do sistema e o único que permanece local; publicá-lo por erro de
  configuração é pior que não subir o painel.
- **Porta ocupada impede a inicialização.** Escolher outra porta sozinho é o
  comportamento "gentil" que quebraria todos os links de digests já enviados,
  sem aviso nenhum.
- **Divergência de endereço apenas alerta.** O painel funciona; o que quebra são
  os links de e-mails antigos. Impedir seria desproporcional, silenciar seria a
  falha silenciosa que este produto existe para evitar.

Sem autenticação, e isso é escolha e não esquecimento: a proteção vem de escutar
apenas em loopback, numa máquina pessoal. Senha em serviço exposto protegeria
menos.
"""

from __future__ import annotations

import logging
import socket

from ..classificacao import custo
from ..config import Config, validar_interface_loopback
from ..log import obter, registrar
from . import confirmacao as CONF
from . import filtros as F
from . import visao_periodo as VP
from .registro import entradas_ordenadas, localizar

_log = obter("painel")

BASE_HTML = """<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ titulo }}</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;
      line-height:1.5;color:#1a1a1a}
 a{color:#0b5}
 .n{display:flex;gap:1.5rem;flex-wrap:wrap;margin:1.5rem 0}
 .n div{border:1px solid #ddd;border-radius:.5rem;padding:.75rem 1rem;min-width:7rem}
 .n b{display:block;font-size:1.6rem}
 .meta{color:#666;font-size:.85rem}
 .falha{border-left:3px solid #c33;padding-left:.6rem}
 .reuniao{border-left:3px solid #38c;padding-left:.6rem}
 li{margin:.6rem 0}
 form{display:inline}
 button{font:inherit;padding:.4rem .9rem;border-radius:.4rem;border:1px solid #999;
        background:#f6f6f6;cursor:pointer}
 pre{white-space:pre-wrap;background:#f7f7f7;padding:1rem;border-radius:.5rem}
</style></head><body>
<p><a href="/">← painel</a></p>
{{ corpo }}
</body></html>"""


def _pagina(titulo: str, corpo: str) -> str:
    return BASE_HTML.replace("{{ titulo }}", titulo).replace("{{ corpo }}", corpo)


def _escapar(texto: str) -> str:
    from html import escape

    return escape(texto or "")


class PortaOcupada(Exception):
    """Falhar é correto: escolher outra porta quebraria os links do digest."""


def verificar_porta_livre(interface: str, porta: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
        teste.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            teste.bind((interface if interface != "localhost" else "127.0.0.1", porta))
        except OSError as erro:
            raise PortaOcupada(
                f"a porta {porta} já está em uso. O painel não sobe em outra "
                "porta automaticamente: isso quebraria os links de todos os "
                "digests já enviados. Libere a porta ou ajuste PAINEL_PORTA e "
                "PAINEL_URL_BASE juntos."
            ) from erro


def anunciar(cfg: Config) -> str:
    """RF-17. Diz onde está escutando e alerta se divergir do digest."""
    efetivo = f"http://{cfg.painel_interface}:{cfg.painel_porta}"
    registrar(_log, logging.INFO, "painel escutando", endereco=efetivo)

    for alerta in cfg.alertas:
        registrar(_log, logging.WARNING, alerta)
    return efetivo


def criar_app(cfg: Config):
    from flask import Flask, abort, redirect, request

    app = Flask(__name__)
    raiz, indice = cfg.acervo_pasta, cfg.acervo_indice_arquivo

    @app.get("/")
    def inicio():
        entradas = entradas_ordenadas(raiz, indice)
        inicio_p, fim_p = VP.limites_do_periodo(modo=cfg.painel_periodo_padrao)
        visao = VP.calcular(entradas, inicio_p, fim_p)

        visiveis = F.filtrar(
            entradas,
            estado=request.args.get("estado") or None,
            tipo=request.args.get("tipo") or None,
            incluir_descartados=cfg.painel_exibir_descartados,
        )
        termo = request.args.get("q", "").strip()
        if termo:
            visiveis = F.buscar(visiveis, termo, raiz)
        visiveis = visiveis[: cfg.painel_itens_por_pagina]

        # T056: custo acumulado do período. Sem teto definido pelo usuário, é
        # esta linha que impede a conta de surpreender — e ela cresce justamente
        # quando o sistema está dando certo.
        gastos = custo.somar_periodo(
            cfg.acervo_indice_arquivo.parent / "custos.jsonl", inicio_p, fim_p
        )
        if gastos["custo_desconhecido"]:
            texto_custo = f'{gastos["chamadas"]}<span style="font-size:.8rem"> chamadas</span>'
        else:
            texto_custo = f'R$ {gastos["custo_estimado"]:.2f}'

        contagens = "".join(
            f"<div><b>{valor}</b>{rotulo}</div>"
            for rotulo, valor in (
                ("capturados", visao.total_capturados),
                ("viraram ação", visao.total_executados),
                ("pendentes", visao.total_pendentes),
                ("descartados", visao.total_descartados),
                ("sem classificação", visao.total_com_falha),
                ("de reunião", visao.total_reunioes),
                ("custo do período", texto_custo),
            )
        )
        meta = (
            "✅ meta de 4 ações no período atingida"
            if visao.meta_mensal_atingida
            else f"faltam {4 - visao.total_executados} para a meta de 4 ações no período"
        )

        itens = "".join(
            f'<li class="{"falha" if not e.classificado else ("reuniao" if e.origem == "reuniao" else "")}">'
            f'<a href="/registro/{e.id}">{_escapar(e.assunto) or "(sem assunto)"}</a>'
            f'<div class="meta">{e.capturado_em[:16].replace("T", " ")} · {e.tipo or "sem tipo"}'
            f' · {e.estado}{" · reunião" if e.origem == "reuniao" else ""}'
            f'{" · não classificado" if not e.classificado else ""}</div></li>'
            for e in visiveis
        )
        if not itens:
            itens = (
                "<li>Nenhum registro ainda. A captura acontece pelo Telegram; "
                "grave uma mensagem de voz para o bot.</li>"
            )

        busca = (
            '<form method="get" action="/">'
            f'<input name="q" value="{_escapar(termo)}" placeholder="buscar">'
            "<button>buscar</button></form>"
        )
        # T057 e T058: a cor sozinha não informa nada. A legenda existe para o
        # usuário saber o que está olhando — sobretudo no caso de reunião, que
        # sinaliza fala de terceiros no registro.
        legenda = (
            "<p class='meta'>"
            "<span class='falha'>vermelho</span>: sem classificação · "
            "<span class='reuniao'>azul</span>: reunião, contém fala de terceiros"
            "</p>"
            if any(not e.classificado or e.origem == "reuniao" for e in visiveis)
            else ""
        )
        return _pagina(
            "Memory Card",
            f"<h1>Memory Card</h1><p class='meta'>{meta}</p>"
            f'<div class="n">{contagens}</div>{busca}{legenda}<ul>{itens}</ul>',
        )

    @app.get("/registro/<identificador>")
    def ver(identificador: str):
        achado = localizar(identificador, raiz, indice)
        if achado is None:
            abort(404)

        reg = achado.registro
        passos = "".join(f"<li>{_escapar(p)}</li>" for p in reg.proximos_passos)
        marcar = "".join(
            f'<a href="{CONF.url_de_marcacao("", identificador, acao)}">'
            f"marcar como {acao}</a> "
            for acao in ("executado", "descartado")
        )
        aviso = (
            "<p class='falha'>Registro não classificado: "
            f"{_escapar(reg.motivo_nao_classificado)}</p>"
            if not reg.classificado
            else ""
        )
        terceiros = (
            "<p class='reuniao'>Origem: reunião — contém fala de terceiros.</p>"
            if reg.contem_terceiros
            else ""
        )
        return _pagina(
            reg.assunto or identificador,
            f"<h1>{_escapar(reg.assunto) or '(sem assunto)'}</h1>"
            f"<p class='meta'>{reg.capturado_em:%d/%m/%Y %H:%M} · {reg.tipo or 'sem tipo'} "
            f"· {reg.estado.value}</p>{aviso}{terceiros}"
            f"<h2>Próximos passos</h2><ul>{passos or '<li>nenhum</li>'}</ul>"
            f"<p>{marcar}</p>"
            f"<h2>Texto bruto</h2><pre>{_escapar(reg.texto_bruto)}</pre>",
        )

    # ---- marcação em duas etapas -------------------------------------------

    @app.get("/registro/<identificador>/marcar/<acao>")
    def confirmar(identificador: str, acao: str):
        """Leitura. **Nunca altera estado** — só mostra o que aconteceria."""
        try:
            situacao = CONF.preparar(identificador, acao, raiz, indice)
        except CONF.AcaoDesconhecida as erro:
            return _pagina("Ação inválida", f"<h1>Ação inválida</h1><p>{erro}</p>"), 400

        if not situacao.encontrado:
            return _pagina(
                "Registro não encontrado",
                f"<h1>Registro não encontrado</h1><p>{situacao.mensagem}</p>",
            ), 200

        if situacao.ja_no_estado:
            return _pagina(
                "Nada a fazer",
                f"<h1>{_escapar(situacao.assunto)}</h1><p>{situacao.mensagem}</p>",
            )

        passos = "".join(f"<li>{_escapar(p)}</li>" for p in situacao.proximos_passos)
        return _pagina(
            f"Marcar como {acao}",
            f"<h1>{_escapar(situacao.assunto)}</h1>"
            f"<p class='meta'>estado atual: {situacao.estado_atual}</p>"
            f"<ul>{passos}</ul>"
            f'<form method="post"><button>Confirmar: marcar como {acao}</button></form>',
        )

    @app.post("/registro/<identificador>/marcar/<acao>")
    def aplicar(identificador: str, acao: str):
        """Envio explícito. Só aqui o estado muda."""
        try:
            situacao = CONF.aplicar(identificador, acao, raiz, indice)
        except CONF.AcaoDesconhecida as erro:
            return _pagina("Ação inválida", f"<h1>Ação inválida</h1><p>{erro}</p>"), 400

        return _pagina(
            "Pronto",
            f"<h1>{_escapar(situacao.assunto) or 'Registro'}</h1>"
            f"<p>{situacao.mensagem}</p><p><a href='/'>voltar ao painel</a></p>",
        )

    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return _pagina("Não encontrado", "<h1>Não encontrado</h1>"), 404

    return app


def iniciar(cfg: Config) -> None:
    """Ponto de entrada do painel. Recusa iniciar antes de expor qualquer coisa."""
    validar_interface_loopback(cfg.painel_interface)   # RF-16
    verificar_porta_livre(cfg.painel_interface, cfg.painel_porta)
    anunciar(cfg)

    app = criar_app(cfg)
    app.run(host=cfg.painel_interface, port=cfg.painel_porta, debug=False)
