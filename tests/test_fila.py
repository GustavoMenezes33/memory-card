"""T015 — retomada da fila sem duplicar nem repetir etapa concluída.

Duas garantias, e a segunda é a que custa dinheiro:

1. **Exatamente uma vez.** Um reinício no meio do processamento não pode gerar
   dois registros para a mesma mensagem.
2. **Não repetir etapa concluída.** Uma queda entre a transcrição e a
   classificação custa a classificação, não a transcrição de novo — que é a
   etapa cara em tempo de máquina.

A ordem de persistência é o que garante as duas: cada etapa é gravada **depois**
de terminar. Persistir antes trocaria duplicata por perda — e perda é
inaceitável, enquanto uma etapa repetida é apenas cara.
"""

from __future__ import annotations

from pathlib import Path

from memory_card.fila import modelo as FM
from memory_card.fila.executor import ExecutorSerial
from memory_card.fila.maquina import Maquina


def esteira(registradas: list[str]) -> dict:
    def etapa(nome: str, **campos):
        def executar(item: FM.ItemFila) -> dict:
            registradas.append(nome)
            return campos
        return executar

    return {
        FM.Etapa.RECEBIDO: etapa("baixar", audio_path="/tmp/audio.ogg"),
        FM.Etapa.BAIXADO: etapa("transcrever", texto_bruto="transcricao"),
        FM.Etapa.TRANSCRITO: etapa("classificar"),
        FM.Etapa.CLASSIFICADO: etapa("arquivar", registro_id="reg-1"),
    }


def item(identificador: str = "i1", **campos) -> FM.ItemFila:
    return FM.ItemFila(
        id=identificador, telegram_message_id=1, telegram_chat_id=42, **campos
    )


def test_esteira_completa_executa_as_quatro_etapas(tmp_path: Path):
    feitas: list[str] = []
    executor = ExecutorSerial(tmp_path, Maquina(tmp_path, esteira(feitas)))

    final = executor.processar_um(executor.enfileirar(item()))

    assert feitas == ["baixar", "transcrever", "classificar", "arquivar"]
    assert final.etapa is FM.Etapa.ARQUIVADO
    assert final.concluido


def test_retomada_nao_repete_transcricao_concluida(tmp_path: Path):
    """A garantia que economiza a etapa cara."""
    feitas: list[str] = []
    executor = ExecutorSerial(tmp_path, Maquina(tmp_path, esteira(feitas)))

    interrompido = item("i2", etapa=FM.Etapa.TRANSCRITO, texto_bruto="ja transcrito")
    executor.enfileirar(interrompido)
    executor.processar_um(interrompido)

    assert "transcrever" not in feitas
    assert feitas == ["classificar", "arquivar"]


def test_item_concluido_nao_e_reprocessado(tmp_path: Path):
    feitas: list[str] = []
    executor = ExecutorSerial(tmp_path, Maquina(tmp_path, esteira(feitas)))

    concluido = item("i3", etapa=FM.Etapa.ARQUIVADO)
    executor.processar_um(concluido)

    assert feitas == []


def test_estado_e_persistido_a_cada_etapa(tmp_path: Path):
    """É o que permite retomar: o disco sabe onde parou, não a memória."""
    vistos: list[FM.Etapa] = []

    def espiar(nome: str, **campos):
        def executar(it: FM.ItemFila) -> dict:
            # Lê do disco o que foi persistido até aqui.
            vistos.append(FM.carregar(FM.caminho_do_item(tmp_path, it.id)).etapa)
            return campos
        return executar

    executores = {
        FM.Etapa.RECEBIDO: espiar("baixar", audio_path="/a.ogg"),
        FM.Etapa.BAIXADO: espiar("transcrever", texto_bruto="t"),
        FM.Etapa.TRANSCRITO: espiar("classificar"),
        FM.Etapa.CLASSIFICADO: espiar("arquivar"),
    }
    executor = ExecutorSerial(tmp_path, Maquina(tmp_path, executores))
    executor.processar_um(executor.enfileirar(item("i4")))

    assert vistos == [
        FM.Etapa.RECEBIDO,
        FM.Etapa.BAIXADO,
        FM.Etapa.TRANSCRITO,
        FM.Etapa.CLASSIFICADO,
    ]


def test_falha_registra_motivo_e_para_o_item(tmp_path: Path):
    def explodir(it: FM.ItemFila) -> dict:
        raise RuntimeError("provedor caiu")

    executor = ExecutorSerial(
        tmp_path, Maquina(tmp_path, {FM.Etapa.RECEBIDO: explodir})
    )
    final = executor.processar_um(executor.enfileirar(item("i5")))

    assert final.etapa is FM.Etapa.FALHOU
    assert "provedor caiu" in final.ultimo_erro
    assert final.tentativas == 1


def test_falha_de_um_item_nao_impede_os_demais(tmp_path: Path):
    """Um item ruim não pode travar a fila inteira."""
    feitas: list[str] = []
    executores = esteira(feitas)

    def explodir_no_primeiro(it: FM.ItemFila) -> dict:
        if it.id == "ruim":
            raise RuntimeError("audio corrompido")
        feitas.append("baixar")
        return {"audio_path": "/a.ogg"}

    executores[FM.Etapa.RECEBIDO] = explodir_no_primeiro
    executor = ExecutorSerial(tmp_path, Maquina(tmp_path, executores))

    executor.enfileirar(item("ruim"))
    executor.enfileirar(item("bom"))
    processados = executor.drenar()

    por_id = {p.id: p for p in processados}
    assert por_id["ruim"].etapa is FM.Etapa.FALHOU
    assert por_id["bom"].etapa is FM.Etapa.ARQUIVADO


def test_pendentes_sobrevivem_ao_reinicio(tmp_path: Path):
    """A fila mora em disco, então uma rajada interrompida continua depois."""
    feitas: list[str] = []
    primeiro = ExecutorSerial(tmp_path, Maquina(tmp_path, esteira(feitas)))
    primeiro.enfileirar(item("a"))
    primeiro.enfileirar(item("b"))

    # Nada foi processado. Simula o processo caindo aqui.
    retomado = ExecutorSerial(tmp_path, Maquina(tmp_path, esteira(feitas)))
    pendentes = retomado.pendentes()

    assert {p.id for p in pendentes} == {"a", "b"}


def test_drenar_respeita_ordem_de_chegada(tmp_path: Path):
    ordem: list[str] = []

    def registrar(it: FM.ItemFila) -> dict:
        ordem.append(it.id)
        return {}

    executores = {etapa: registrar for etapa in FM.Etapa if etapa is not FM.Etapa.FALHOU}
    executor = ExecutorSerial(tmp_path, Maquina(tmp_path, executores))

    for identificador, momento in (("z", "2026-08-11T10:00:00"), ("a", "2026-08-11T09:00:00")):
        executor.enfileirar(item(identificador, enfileirado_em=momento))
    executor.drenar()

    assert ordem[0] == "a", "o mais antigo precisa ser processado primeiro"


def test_etapa_sem_executor_falha_em_vez_de_travar(tmp_path: Path):
    executor = ExecutorSerial(tmp_path, Maquina(tmp_path, {}))
    final = executor.processar_um(executor.enfileirar(item("i6")))

    assert final.etapa is FM.Etapa.FALHOU
    assert "sem executor" in final.ultimo_erro


def test_item_corrompido_no_disco_e_ignorado(tmp_path: Path):
    """Um arquivo de fila ilegível não pode derrubar a listagem."""
    executor = ExecutorSerial(tmp_path, Maquina(tmp_path, {}))
    executor.enfileirar(item("bom"))
    (tmp_path / "corrompido.json").write_text("{ isso nao e json", encoding="utf-8")

    assert {p.id for p in executor.pendentes()} == {"bom"}
