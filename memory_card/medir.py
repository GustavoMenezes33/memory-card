"""T060 — instrumento de medição da qualidade da classificação.

Este módulo é o que restou do teste Mago de Oz, removido do plano em 2026-08-11
por decisão do usuário, dado o caráter também acadêmico do projeto.

O portão caiu; a medição não. Sem um número registrado, nenhum ajuste futuro de
prompt terá referência para comparação — "melhorou" vira impressão, e o item
correspondente do critério de pronto fica impossível de fechar.

**A medição precisa usar transcrições reais do Whisper, não texto digitado.**
Texto limpo mede a classificação sobre a melhor entrada possível e produz um
número otimista que o sistema real não reproduz: a entrada verdadeira vem de
áudio com ruído de trânsito e fala ao volante.

Uso:

    python -m memory_card.medir  <pasta-com-audios>

Grava o resultado em `_reversa_forward/001-captura-voz-ao-arquivo/medicao-classificacao.md`.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import config as C
from . import log as L
from .classificacao import adaptador as _adaptadores  # noqa: F401 — registra
from .classificacao.erros import ErroDeClassificacao
from .classificacao.fronteira import PedidoClassificacao, obter_adaptador
from .transcricao import politica as P
from .transcricao.whisper_local import ErroDeTranscricao, transcrever

AMOSTRA_MINIMA = 20
CORTE_CONCORDANCIA = 0.80   # 4 em 5


@dataclass
class Amostra:
    arquivo: str
    texto_bruto: str
    assunto: str = ""
    tipo: str = ""
    proximos_passos: tuple[str, ...] = ()
    erro: str = ""
    concordou: bool | None = None   # preenchido pelo julgamento humano


def transcrever_pasta(cfg: C.Config, pasta: Path) -> list[Amostra]:
    amostras: list[Amostra] = []
    audios = sorted(
        p for p in pasta.iterdir()
        if p.suffix.lower() in {".ogg", ".oga", ".mp3", ".m4a", ".wav"}
    )

    for audio in audios:
        try:
            resultado = transcrever(
                audio,
                modelo=cfg.whisper_modelo,
                idioma=cfg.whisper_idioma,
                dispositivo=cfg.whisper_dispositivo,
                pasta_modelos=cfg.whisper_pasta_modelos,
                timeout_s=cfg.whisper_timeout_longo_s,
            )
            amostras.append(Amostra(audio.name, resultado.texto_bruto))
        except ErroDeTranscricao as erro:
            amostras.append(Amostra(audio.name, "", erro=f"transcrição: {erro}"))
    return amostras


def classificar_amostras(cfg: C.Config, amostras: list[Amostra]) -> list[Amostra]:
    adaptador = obter_adaptador(
        cfg.llm_provedor, api_key=cfg.llm_api_key, endpoint=cfg.llm_endpoint
    )
    prompt = cfg.llm_prompt_arquivo.read_text(encoding="utf-8")

    for amostra in amostras:
        if amostra.erro or not amostra.texto_bruto.strip():
            continue
        try:
            resultado = adaptador.classificar(
                PedidoClassificacao(
                    texto_bruto=amostra.texto_bruto,
                    tipos_permitidos=cfg.llm_tipos_registro,
                    prompt=prompt,
                    modelo=cfg.llm_modelo,
                    timeout_s=cfg.llm_timeout_s,
                )
            )
            amostra.assunto = resultado.assunto
            amostra.tipo = resultado.tipo
            amostra.proximos_passos = resultado.proximos_passos
        except ErroDeClassificacao as erro:
            amostra.erro = f"classificação: {erro}"
    return amostras


def julgar_no_terminal(amostras: list[Amostra]) -> list[Amostra]:
    """Uma amostra por vez. O julgamento é humano e não pode ser automatizado.

    A pergunta é sempre a mesma: você aceitaria este registro **sem corrigir**?
    Não é "está bom", é "você confiaria sem conferir" — porque confiança em
    automação é binária na prática.
    """
    for indice, amostra in enumerate(amostras, start=1):
        print("\n" + "─" * 70)
        print(f"[{indice}/{len(amostras)}] {amostra.arquivo}")
        if amostra.erro:
            print(f"  ERRO: {amostra.erro}")
            amostra.concordou = False
            continue

        print(f"\n  transcrição: {amostra.texto_bruto[:400]}")
        print(f"\n  assunto: {amostra.assunto}")
        print(f"  tipo:    {amostra.tipo}")
        for passo in amostra.proximos_passos:
            print(f"  passo:   {passo}")

        resposta = input("\n  Aceitaria sem corrigir? [s/n] ").strip().lower()
        amostra.concordou = resposta.startswith("s")
    return amostras


def relatorio(amostras: list[Amostra], cfg: C.Config) -> str:
    julgadas = [a for a in amostras if a.concordou is not None]
    aceitas = sum(1 for a in julgadas if a.concordou)
    taxa = aceitas / len(julgadas) if julgadas else 0.0
    aprovou = taxa >= CORTE_CONCORDANCIA
    agora = datetime.now(timezone.utc)

    linhas = [
        "# Medição da qualidade da classificação",
        "",
        f"> Data: {agora:%Y-%m-%d}",
        f"> Provedor: {cfg.llm_provedor} · modelo: {cfg.llm_modelo}",
        f"> Modelo de transcrição: {cfg.whisper_modelo}",
        f"> Tipos configurados: {', '.join(cfg.llm_tipos_registro)}",
        "",
        "## Resultado",
        "",
        f"| Amostras julgadas | {len(julgadas)} |",
        "|---|---|",
        f"| Aceitas sem correção | {aceitas} |",
        f"| Taxa de concordância | **{taxa:.0%}** |",
        f"| Corte de referência | {CORTE_CONCORDANCIA:.0%} (4 em 5) |",
        f"| Veredito | **{'acima' if aprovou else 'abaixo'} do corte** |",
        "",
    ]

    if len(julgadas) < AMOSTRA_MINIMA:
        linhas += [
            f"⚠️ **Amostra pequena.** {len(julgadas)} registros, abaixo dos "
            f"{AMOSTRA_MINIMA} recomendados. O número é indicativo, não conclusivo.",
            "",
        ]

    if not aprovou:
        linhas += [
            "## O que fazer com um resultado abaixo do corte",
            "",
            "Este número **não bloqueia nada** — o portão foi removido do plano. "
            "Ele indica, em ordem de custo crescente:",
            "",
            "1. Ajustar `config/prompt_classificacao.txt`, que é a alavanca mais barata.",
            "2. Revisar `LLM_TIPOS_REGISTRO`: um tipo que nunca é atribuído, ou "
            "registros recorrentes que não cabem em nenhum, indicam lista errada.",
            "3. Trocar de modelo ou de provedor, o que a fronteira única permite "
            "sem tocar no restante do sistema.",
            "4. Reduzir o escopo ao resurfacing simples, que era a Opção D da ideação.",
            "",
            "Repita a medição depois de cada ajuste e compare com este número.",
            "",
        ]

    linhas += ["## Amostras", "", "| # | Arquivo | Assunto atribuído | Tipo | Aceita |", "|---|---|---|---|---|"]
    for indice, amostra in enumerate(amostras, start=1):
        marca = "—" if amostra.concordou is None else ("sim" if amostra.concordou else "não")
        assunto = amostra.erro or amostra.assunto or "(vazio)"
        linhas.append(f"| {indice} | `{amostra.arquivo}` | {assunto} | {amostra.tipo or '—'} | {marca} |")

    linhas += [
        "",
        "## Tipos observados",
        "",
    ]
    observados: dict[str, int] = {}
    for amostra in amostras:
        if amostra.tipo:
            observados[amostra.tipo] = observados.get(amostra.tipo, 0) + 1
    for tipo in cfg.llm_tipos_registro:
        quantidade = observados.get(tipo, 0)
        nota = " ← nunca atribuído" if quantidade == 0 else ""
        linhas.append(f"- `{tipo}`: {quantidade}{nota}")

    linhas += [
        "",
        "---",
        "Gerado por `python -m memory_card.medir`",
    ]
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    argumentos = argv if argv is not None else sys.argv[1:]
    if not argumentos:
        print(__doc__)
        return 2

    pasta = Path(argumentos[0])
    if not pasta.is_dir():
        print(f"pasta não encontrada: {pasta}", file=sys.stderr)
        return 2

    cfg = C.carregar()
    L.configurar(cfg.log_nivel)

    print(f"Transcrevendo áudios de {pasta}…")
    amostras = transcrever_pasta(cfg, pasta)
    if not amostras:
        print("nenhum áudio encontrado", file=sys.stderr)
        return 1

    print(f"Classificando {len(amostras)} amostras…")
    amostras = classificar_amostras(cfg, amostras)
    amostras = julgar_no_terminal(amostras)

    destino = Path("_reversa_forward/001-captura-voz-ao-arquivo/medicao-classificacao.md")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(relatorio(amostras, cfg), encoding="utf-8")

    bruto = destino.with_suffix(".jsonl")
    with bruto.open("w", encoding="utf-8") as saida:
        for amostra in amostras:
            saida.write(json.dumps(asdict(amostra), ensure_ascii=False) + "\n")

    print(f"\nRelatório: {destino}")
    print(f"Dados brutos: {bruto}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
