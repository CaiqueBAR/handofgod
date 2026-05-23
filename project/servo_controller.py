from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import serial

from .utils import open_serial_with_retries, rank_candidate_ports


@dataclass(frozen=True)
class ServoCommand:
    name: str
    sent_at: float


class ServoSerialController:
    def __init__(
        self,
        port: str = "auto",
        baud: int = 115200,
        timeout_s: float = 1.0,
        open_timeout_s: float = 2.0,
        dtr: Optional[bool] = None,
        rts: Optional[bool] = None,
        open_retries: int = 3,
        retry_delay_s: float = 1.0,
    ):
        self._port = port
        self._baud = baud
        self._timeout_s = timeout_s
        self._open_timeout_s = open_timeout_s
        self._dtr = dtr
        self._rts = rts
        self._open_retries = open_retries
        self._retry_delay_s = retry_delay_s
        self._serial: Optional[serial.Serial] = None

        self._last_cmd: Optional[ServoCommand] = None

    def open(self) -> None:
        if self._serial is not None and self._serial.is_open:
            return
        candidates = rank_candidate_ports() if self._port == "auto" else [self._port]
        self._serial = open_serial_with_retries(
            candidate_ports=candidates,
            baud=self._baud,
            timeout_s=self._timeout_s,
            dtr=self._dtr,
            rts=self._rts,
            open_timeout_s=self._open_timeout_s,
            retries=self._open_retries,
            retry_delay_s=self._retry_delay_s,
        )

    def close(self) -> None:
        if self._serial is None:
            return
        try:
            self._serial.close()
        finally:
            self._serial = None

    def send(self, command: str) -> ServoCommand:
        if self._serial is None:
            self.open()
        assert self._serial is not None
        line = command.strip() + "\n"
        self._serial.write(line.encode("utf-8"))
        self._last_cmd = ServoCommand(name=command.strip(), sent_at=time.time())
        return self._last_cmd

    @property
    def last_command(self) -> Optional[ServoCommand]:
        return self._last_cmd


DEFAULT_LABEL_TO_COMMAND: dict[str, str] = {
    "mao_aberta": "OPEN_HAND",
    "mao_fechada": "CLOSE_HAND",
    "flexao": "FLEX",
    "extensao": "EXTEND",
}

