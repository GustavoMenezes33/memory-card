"""T032 — classificação de áudio longo em duas passagens.

O achado que este módulo resolve não é técnico, é de modelagem: **as specs
assumem que um áudio contém um insight.** Verdade para trinta segundos ao
volante, falso para quarenta e cinco minutos de reunião.

Pedir "um assunto" a uma transcrição multiassunto produz um registro do tipo
"reunião sobre diversos temas" com um único próximo passo — um registro sem
valor nenhum. Daí a decisão D-03: **um registro, com lista de próximos passos**,
em vez de um só.

Uma correção importante à intuição inicial: **o problema não é o tamanho da
entrada.** Uma fala de quarenta e cinco minutos rende algo em torno de sete mil
palavras, o que cabe com folga nos modelos atuais. O problema é a *qualidade da
saída* quando se pede um assunto único para conteúdo multiassunto. Por isso a
solução é duas passagens, e não truncamento.

Dividir a reunião em N registros continua fora do escopo (NG-03 e EC-07): a
divisão automática erra e gera fragmentos sem contexto, que são piores que um
bloco íntegro. O texto bruto imutável mantém essa evolução possível depois.
"""

from __future__ import annotations

import re

from .fronteira import Adaptador, Classificacao, PedidoClassificacao, Uso

# Blocos generosos: o corte existe para dar foco ao modelo em cada passagem,
# não para caber no contexto.
PALAVRAS_POR_BLOCO = 1200


# Além deste múltiplo do alvo, corta mesmo sem fronteira de frase.
TOLERANCIA_SEM_PONTUACAO = 1.5


def dividir_em_blocos(texto: str, palavras_por_bloco: int = PALAVRAS_POR_BLOCO) -> list[str]:
    """Divide preferindo fronteira de frase, com corte forçado como rede.

    A preferência por frase existe para não cortar no meio de uma ideia. O corte
    forçado existe porque **transcrição de áudio ruidoso frequentemente não tem
    pontuação confiável** — e sem ele uma reunião inteira voltaria como bloco
    único, a segunda passagem nunca aconteceria, e o registro sairia com um
    assunto genérico: exatamente o defeito que este módulo existe para evitar.
    """
    palavras = texto.split()
    if len(palavras) <= palavras_por_bloco:
        return [texto.strip()] if texto.strip() else []

    limite_rigido = int(palavras_por_bloco * TOLERANCIA_SEM_PONTUACAO)
    blocos: list[str] = []
    atual: list[str] = []

    for palavra in palavras:
        atual.append(palavra)
        atingiu_alvo = len(atual) >= palavras_por_bloco
        fim_de_frase = bool(re.search(r"[.!?]$", palavra))
        if (atingiu_alvo and fim_de_frase) or len(atual) >= limite_rigido:
            blocos.append(" ".join(atual))
            atual = []

    if atual:
        # Sobra curta demais para valer uma chamada própria: junta à anterior.
        if blocos and len(atual) < palavras_por_bloco // 4:
            blocos[-1] = blocos[-1] + " " + " ".join(atual)
        else:
            blocos.append(" ".join(atual))
    return blocos


def classificar_longo(
    adaptador: Adaptador,
    pedido: PedidoClassificacao,
) -> Classificacao:
    """Extrai por blocos, depois consolida.

    A primeira passagem roda uma vez por bloco e cada uma enxerga só o seu
    trecho. A segunda recebe os assuntos e encaminhamentos já extraídos — texto
    curto — e produz o registro final.
    """
    blocos = dividir_em_blocos(pedido.texto_bruto)

    if len(blocos) <= 1:
        # Reunião curta o bastante para uma passagem só. Não vale pagar duas.
        return adaptador.classificar(pedido)

    parciais: list[Classificacao] = []
    tokens_entrada = tokens_saida = 0
    provedor = modelo = ""

    for bloco in blocos:
        parcial = adaptador.classificar(
            PedidoClassificacao(
                texto_bruto=bloco,
                tipos_permitidos=pedido.tipos_permitidos,
                prompt=pedido.prompt,
                modelo=pedido.modelo,
                timeout_s=pedido.timeout_s,
                multiplos_passos=True,
            )
        )
        parciais.append(parcial)
        tokens_entrada += parcial.uso.tokens_entrada
        tokens_saida += parcial.uso.tokens_saida
        provedor = provedor or parcial.uso.provedor
        modelo = modelo or parcial.uso.modelo

    resumo = "\n".join(
        f"- {p.assunto}: " + "; ".join(p.proximos_passos) for p in parciais
    )
    consolidacao = adaptador.classificar(
        PedidoClassificacao(
            texto_bruto=(
                "Abaixo estão os temas e encaminhamentos extraídos de uma reunião, "
                "bloco a bloco. Produza um assunto único que a nomeie e a lista "
                "consolidada de próximos passos, sem repetir itens equivalentes.\n\n"
                + resumo
            ),
            tipos_permitidos=pedido.tipos_permitidos,
            prompt=pedido.prompt,
            modelo=pedido.modelo,
            timeout_s=pedido.timeout_s,
            multiplos_passos=True,
        )
    )

    tokens_entrada += consolidacao.uso.tokens_entrada
    tokens_saida += consolidacao.uso.tokens_saida

    return Classificacao(
        assunto=consolidacao.assunto,
        tipo=consolidacao.tipo,
        proximos_passos=consolidacao.proximos_passos,
        multiplos_temas=True,   # por construção: houve mais de um bloco
        uso=Uso(
            provedor=provedor or consolidacao.uso.provedor,
            modelo=modelo or consolidacao.uso.modelo,
            tokens_entrada=tokens_entrada,
            tokens_saida=tokens_saida,
        ),
    )
