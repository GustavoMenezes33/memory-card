"""T013 — escrita atômica.

A garantia: **ou o arquivo existe íntegro, ou não existe.** Nunca um arquivo
pela metade.

Arquivo parcial é indistinguível de arquivo corrompido, e um acervo em que o
usuário não pode confiar deixa de ser acervo. Como o produto inteiro se apoia na
promessa de que o insight está guardado, este é o teste que protege a promessa.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from memory_card.acervo import escrita as E
from memory_card.acervo.leitura import ler_registro
from memory_card.acervo.modelo import Origem, Registro

QUANDO = datetime(2026, 8, 11, 14, 30, 52, tzinfo=timezone.utc)


def registro(texto: str = "conteudo original") -> Registro:
    return Registro(
        id="20260811-143052-aaaaaa",
        capturado_em=QUANDO,
        origem=Origem.VOZ,
        texto_bruto=texto,
        assunto="Assunto de teste",
        tipo="ideia",
        proximos_passos=("Fazer alguma coisa",),
    )


def test_gravacao_normal_produz_arquivo_legivel(tmp_path: Path):
    destino = tmp_path / "2026-08" / "registro.md"
    E.gravar_registro(destino, registro())

    assert destino.exists()
    assert ler_registro(destino).texto_bruto == "conteudo original"


def test_nenhum_temporario_sobra_apos_gravacao(tmp_path: Path):
    destino = tmp_path / "registro.md"
    E.gravar_registro(destino, registro())

    assert list(tmp_path.glob(".tmp-*")) == []


def test_interrupcao_na_escrita_nao_cria_o_destino(tmp_path: Path, monkeypatch):
    """Falha durante a escrita: o destino nunca chega a existir."""
    destino = tmp_path / "registro.md"

    original = os.fdopen

    def falhar(*args, **kwargs):
        arquivo = original(*args, **kwargs)
        arquivo.close()
        raise OSError("interrupção simulada durante a escrita")

    monkeypatch.setattr(os, "fdopen", falhar)

    with pytest.raises(OSError):
        E.gravar_registro(destino, registro())

    assert not destino.exists(), "o destino não pode existir se a escrita falhou"
    assert list(tmp_path.glob(".tmp-*")) == [], "temporário ficou para trás"


def test_interrupcao_na_renomeacao_preserva_o_arquivo_anterior(tmp_path: Path, monkeypatch):
    """O caso mais perigoso: já existe um registro e a regravação falha.

    O conteúdo antigo precisa continuar lá. Perder o registro anterior ao tentar
    atualizá-lo seria a pior falha possível deste componente.
    """
    destino = tmp_path / "registro.md"
    E.gravar_registro(destino, registro("conteudo original"))

    def falhar(*args, **kwargs):
        raise OSError("interrupção simulada durante a renomeação")

    monkeypatch.setattr(os, "replace", falhar)

    with pytest.raises(OSError):
        E.gravar_registro(destino, registro("conteudo novo"))

    assert ler_registro(destino).texto_bruto == "conteudo original"
    assert list(tmp_path.glob(".tmp-*")) == []


def test_disco_cheio_vira_erro_nomeado(tmp_path: Path, monkeypatch):
    """EC-03. Erro explícito antes de deixar arquivo parcial."""
    destino = tmp_path / "registro.md"

    def sem_espaco(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", sem_espaco)

    with pytest.raises(E.EspacoInsuficiente) as erro:
        E.gravar_registro(destino, registro())

    assert "espaço" in str(erro.value).lower()
    assert not destino.exists()
    assert list(tmp_path.glob(".tmp-*")) == []


def test_regravacao_substitui_integralmente(tmp_path: Path):
    destino = tmp_path / "registro.md"
    E.gravar_registro(destino, registro("primeira versao bem mais longa que a segunda"))
    E.gravar_registro(destino, registro("curta"))

    lido = ler_registro(destino)
    assert lido.texto_bruto == "curta"
    assert "primeira versao" not in destino.read_text(encoding="utf-8")


def test_pastas_intermediarias_sao_criadas(tmp_path: Path):
    destino = tmp_path / "2026-08" / "subpasta" / "registro.md"
    E.gravar_registro(destino, registro())

    assert destino.exists()
