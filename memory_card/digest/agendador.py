"""T053 — agendador interno semanal.

Dentro do processo, e não no agendador do sistema operacional, por dois motivos:
ele difere entre plataformas, e é a peça que o usuário esqueceria de configurar
— fazendo o digest simplesmente nunca chegar, sem erro nenhum. Como o processo
já precisa estar vivo para o long polling, hospedar o agendador nele não custa
nada.

Duas regras que parecem contraditórias e defendem a mesma coisa:

- **Não acumular envios atrasados.** Voltar de duas semanas de viagem e receber
  três digests de uma vez é a forma mais rápida de aprender a ignorá-los.
- **Enviar mesmo sem registros pendentes.** Silêncio é indistinguível de falha.

As duas protegem a confiança no ritual semanal, que é o que o mecanismo tem de
mais frágil.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class RegistroDeEnvios:
    """Guarda a semana do último envio. É o que garante no máximo um por semana."""

    arquivo: Path

    def ultima_semana_enviada(self) -> tuple[int, int] | None:
        if not self.arquivo.exists():
            return None
        try:
            dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
            return int(dados["ano"]), int(dados["semana"])
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            return None

    def anotar(self, quando: datetime, identificadores: list[str], status: str) -> None:
        ano, semana, _ = quando.isocalendar()
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(
            json.dumps(
                {
                    "ano": ano,
                    "semana": semana,
                    "enviado_em": quando.isoformat(timespec="seconds"),
                    "quantidade": len(identificadores),
                    "registros_incluidos": identificadores,
                    "status": status,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def momento_da_semana(
    referencia: datetime, dia_semana: int, hora: int, minuto: int
) -> datetime:
    """O instante programado dentro da semana da referência."""
    inicio_semana = (referencia - timedelta(days=referencia.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return inicio_semana + timedelta(days=dia_semana, hours=hora, minutes=minuto)


def deve_enviar(
    agora: datetime,
    dia_semana: int,
    hora: int,
    minuto: int,
    ultima: tuple[int, int] | None,
) -> bool:
    """Devido e ainda não enviado nesta semana.

    A verificação é por semana, não por instante. É isso que faz o envio ocorrer
    na primeira execução seguinte quando a máquina estava desligada no horário —
    uma única vez, sem repor os envios das semanas que passaram.
    """
    ano_atual, semana_atual, _ = agora.isocalendar()
    if ultima == (ano_atual, semana_atual):
        return False
    return agora >= momento_da_semana(agora, dia_semana, hora, minuto)


@dataclass
class Agendador:
    registro: RegistroDeEnvios
    dia_semana: int
    hora: int
    minuto: int

    def pendente(self, agora: datetime | None = None) -> bool:
        momento = (agora or datetime.now(timezone.utc)).astimezone()
        return deve_enviar(
            momento,
            self.dia_semana,
            self.hora,
            self.minuto,
            self.registro.ultima_semana_enviada(),
        )

    def concluir(
        self, identificadores: list[str], status: str, agora: datetime | None = None
    ) -> None:
        """Anotar depois de enviar é o que impede o envio duplicado da semana."""
        self.registro.anotar(
            (agora or datetime.now(timezone.utc)).astimezone(), identificadores, status
        )
