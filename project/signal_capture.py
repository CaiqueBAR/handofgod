from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterator, Optional

import serial

from .utils import auto_detect_port_and_baud, open_serial_with_retries, rank_candidate_ports


@dataclass(frozen=True)
class EmgRawSample:
    t: float
    raw: float
    filtered: Optional[float] = None


class SerialSignalCapture:
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
        self._baud = baud
        self._timeout_s = timeout_s
        self._dtr = dtr
        self._rts = rts
        self._open_timeout_s = open_timeout_s
        self._open_retries = open_retries
        self._retry_delay_s = retry_delay_s

        self._serial: Optional[serial.Serial] = None
        self._port = port

    @property
    def port(self) -> str:
        if self._serial is not None:
            return str(self._serial.port)
        return self._port

    def open(self) -> None:
        if self._serial is not None and self._serial.is_open:
            return

        if self._port == "auto":
            candidates = rank_candidate_ports()
            bauds = []
            for b in [int(self._baud), 115200, 57600, 38400, 19200, 9600]:
                if b not in bauds:
                    bauds.append(b)
            detected_port, detected_baud, _probe = auto_detect_port_and_baud(
                preferred_ports=candidates,
                preferred_bauds=bauds,
                timeout_s=float(min(0.3, self._timeout_s)),
                dtr=self._dtr,
                rts=self._rts,
            )
            if detected_port is not None:
                self._port = str(detected_port)
                candidates = [self._port]
                if detected_baud is not None:
                    self._baud = int(detected_baud)
            else:
                candidates = rank_candidate_ports()
        else:
            candidates = [self._port]

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

        try:
            self._serial.reset_input_buffer()
        except Exception:
            pass

    def close(self) -> None:
        if self._serial is None:
            return
        try:
            self._serial.close()
        finally:
            self._serial = None

    def write_line(self, line: str) -> None:
        self.write_text(line, newline="\n")

    def write_text(self, text: str, newline: str = "\n") -> None:
        if self._serial is None:
            raise RuntimeError("serial_not_open")
        data = (text.strip() + str(newline)).encode("utf-8")
        self._serial.write(data)

    def _parse_line_to_values(self, line: str) -> Optional[list[float]]:
        nums = re.findall(r"[-+]?\d+(?:[.,]\d+)?", line)
        if not nums:
            return None
        try:
            values = [float(n.replace(",", ".")) for n in nums]
        except Exception:
            return None
        return values

    def samples(self) -> Iterator[EmgRawSample]:
        if self._serial is None:
            self.open()
        assert self._serial is not None

        while True:
            raw = self._serial.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore").strip()
            values = self._parse_line_to_values(line)
            if not values:
                continue
            raw_value = float(values[0])
            filtered_value = float(values[1]) if len(values) >= 2 else None
            yield EmgRawSample(t=time.time(), raw=raw_value, filtered=filtered_value)
