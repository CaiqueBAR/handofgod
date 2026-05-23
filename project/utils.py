from __future__ import annotations

import json
import multiprocessing
import re
import time
from dataclasses import dataclass
from typing import Optional

import serial
from serial.tools import list_ports


@dataclass(frozen=True)
class SerialPortInfo:
    device: str
    description: str | None
    hwid: str | None
    manufacturer: str | None
    serial_number: str | None


def list_serial_ports() -> list[SerialPortInfo]:
    items: list[SerialPortInfo] = []
    for p in list_ports.comports():
        items.append(
            SerialPortInfo(
                device=p.device,
                description=p.description,
                hwid=p.hwid,
                manufacturer=getattr(p, "manufacturer", None),
                serial_number=getattr(p, "serial_number", None),
            )
        )
    return items


def rank_candidate_ports() -> list[str]:
    ports = list(list_ports.comports())
    preferred: list[str] = []
    others: list[str] = []
    virtual: list[str] = []
    for p in ports:
        d = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        manufacturer = (getattr(p, "manufacturer", None) or "").lower()

        is_shared = "hhd software" in d or "shared serial port" in d or "hhd software" in manufacturer
        is_root_ports = hwid.startswith("root\\ports")
        is_virtual = is_shared or is_root_ports

        is_usb = hwid.startswith("usb ") or "usb" in d or "usb" in manufacturer
        is_arduino_like = "arduino" in d or "ch340" in d or "cp210" in d or "usb serial" in d

        if is_virtual:
            virtual.append(p.device)
        elif is_usb and is_arduino_like:
            preferred.append(p.device)
        elif is_usb:
            preferred.append(p.device)
        else:
            others.append(p.device)
    return preferred + others + virtual


def probe_port_numeric_stream(
    port: str,
    baud: int,
    timeout_s: float,
    read_seconds: float = 0.8,
    dtr: Optional[bool] = None,
    rts: Optional[bool] = None,
) -> dict:
    start = time.time()
    n_numeric = 0
    n_total = 0
    sample_line: Optional[str] = None
    try:
        s = serial.Serial(port=port, baudrate=int(baud), timeout=float(timeout_s))
    except Exception as e:
        return {"ok": False, "error_type": type(e).__name__, "error": str(e)}

    try:
        if dtr is not None:
            s.dtr = bool(dtr)
        if rts is not None:
            s.rts = bool(rts)
        try:
            s.reset_input_buffer()
        except Exception:
            pass

        while (time.time() - start) < float(read_seconds):
            raw = s.readline()
            if not raw:
                continue
            n_total += 1
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if sample_line is None:
                sample_line = line[:120]
            if re.search(r"[-+]?\d+(?:[.,]\d+)?", line):
                n_numeric += 1

        return {"ok": True, "numeric_lines": n_numeric, "total_lines": n_total, "sample": sample_line}
    finally:
        try:
            s.close()
        except Exception:
            pass


def auto_detect_port_and_baud(
    preferred_ports: list[str],
    preferred_bauds: list[int],
    timeout_s: float,
    dtr: Optional[bool],
    rts: Optional[bool],
) -> tuple[Optional[str], Optional[int], dict]:
    best: tuple[int, Optional[str], Optional[int], dict] = (0, None, None, {})
    for port in preferred_ports:
        for baud in preferred_bauds:
            probe = probe_port_numeric_stream(
                port=port,
                baud=int(baud),
                timeout_s=float(timeout_s),
                read_seconds=1.5,
                dtr=dtr,
                rts=rts,
            )
            if not probe.get("ok"):
                continue
            score = int(probe.get("numeric_lines") or 0)
            if score > best[0]:
                best = (score, str(port), int(baud), probe)
            if score >= 2:
                return str(port), int(baud), probe
    return best[1], best[2], best[3]


def _probe_worker(
    port: str,
    baud: int,
    timeout_s: float,
    dtr: Optional[bool],
    rts: Optional[bool],
    out_q: multiprocessing.Queue,
) -> None:
    try:
        s = serial.Serial(port=port, baudrate=baud, timeout=timeout_s)
        if dtr is not None:
            s.dtr = bool(dtr)
        if rts is not None:
            s.rts = bool(rts)
        try:
            s.reset_input_buffer()
        except Exception:
            pass
        s.close()
        out_q.put({"ok": True})
    except Exception as e:
        out_q.put({"ok": False, "error_type": type(e).__name__, "error": str(e)})


def probe_port_openable(
    port: str,
    baud: int,
    timeout_s: float,
    dtr: Optional[bool],
    rts: Optional[bool],
    open_timeout_s: float,
) -> dict:
    ctx = multiprocessing.get_context("spawn")
    out_q: multiprocessing.Queue = ctx.Queue(maxsize=1)
    p = ctx.Process(target=_probe_worker, args=(port, baud, timeout_s, dtr, rts, out_q))
    p.daemon = True
    p.start()
    p.join(open_timeout_s)
    if p.is_alive():
        p.terminate()
        p.join(1.0)
        return {"ok": False, "error_type": "OpenTimeout", "error": f"open_timeout>{open_timeout_s}s"}
    try:
        return out_q.get_nowait()
    except Exception:
        return {"ok": False, "error_type": "ProbeFailed", "error": "no_result"}


def open_serial_with_retries(
    candidate_ports: list[str],
    baud: int,
    timeout_s: float,
    dtr: Optional[bool],
    rts: Optional[bool],
    open_timeout_s: float,
    retries: int,
    retry_delay_s: float,
) -> serial.Serial:
    errors: list[dict] = []
    for port in candidate_ports:
        probe = probe_port_openable(
            port=port,
            baud=baud,
            timeout_s=timeout_s,
            dtr=dtr,
            rts=rts,
            open_timeout_s=open_timeout_s,
        )
        if not probe.get("ok"):
            errors.append({"port": port, "attempt": 0, **probe})
            continue

        for attempt in range(retries + 1):
            try:
                s = serial.Serial(port=port, baudrate=baud, timeout=timeout_s)
                if dtr is not None:
                    s.dtr = bool(dtr)
                if rts is not None:
                    s.rts = bool(rts)
                return s
            except Exception as e:
                errors.append(
                    {
                        "port": port,
                        "attempt": attempt + 1,
                        "error_type": type(e).__name__,
                        "error": str(e),
                    }
                )
                if attempt < retries:
                    time.sleep(retry_delay_s)

    raise RuntimeError(
        json.dumps(
            {
                "ok": False,
                "erro": "nao_foi_possivel_abrir_nenhuma_porta",
                "tried_ports": candidate_ports,
                "portas_detectadas": [p.__dict__ for p in list_serial_ports()],
                "erros": errors[-10:],
                "dicas": [
                    "Feche o Serial Monitor/Serial Plotter do Arduino IDE (eles travam a porta).",
                    "Confirme a porta correta (COMx) e tente rodar com --port COMx.",
                    "Se só aparecer Bluetooth em --list-ports, conecte o Arduino/ESP32 via USB e tente novamente.",
                    "Desconecte e reconecte o dispositivo e tente novamente.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
