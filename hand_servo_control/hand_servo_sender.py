from __future__ import annotations

import argparse
import sys
import time
from typing import Optional


def _import_serial():
    try:
        import serial
        from serial.tools import list_ports
    except Exception as e:
        raise RuntimeError(
            "Dependência ausente: pyserial. Instale com: pip install pyserial\n"
            f"Detalhes: {type(e).__name__}: {e}"
        ) from e
    return serial, list_ports


def list_serial_ports() -> list[dict]:
    _, list_ports = _import_serial()
    items: list[dict] = []
    for p in list_ports.comports():
        items.append(
            {
                "device": p.device,
                "description": getattr(p, "description", None),
                "hwid": getattr(p, "hwid", None),
                "manufacturer": getattr(p, "manufacturer", None),
                "serial_number": getattr(p, "serial_number", None),
            }
        )
    return items


def pick_auto_port() -> Optional[str]:
    ports = list_serial_ports()
    if not ports:
        return None
    preferred = []
    others = []
    for p in ports:
        desc = (p.get("description") or "").lower()
        dev = p.get("device")
        if not dev:
            continue
        if "arduino" in desc or "ch340" in desc or "cp210" in desc or "usb serial" in desc:
            preferred.append(dev)
        else:
            others.append(dev)
    return (preferred + others)[0] if (preferred or others) else None


def print_menu() -> None:
    print("")
    print("Comandos disponíveis (digite o número e pressione Enter):")
    print("  1  -> mover dedo 1 (dedos[0])")
    print("  2  -> mover dedo 2 (dedos[1])")
    print("  3  -> mover dedo 3 (dedos[2])")
    print("  4  -> mover dedo 4 (dedos[3])")
    print("  5  -> mover dedo 5 (dedos[4])")
    print("  6  -> mover pulso")
    print("  7  -> fechar/abrir todos")
    print("  8  -> gesto joinha")
    print("  9  -> gesto paz")
    print("  10 -> gesto rock")
    print("  11 -> acenar")
    print("")
    print("Outros:")
    print("  ports -> listar portas")
    print("  q     -> sair")
    print("")


def read_for(ser, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            waiting = getattr(ser, "in_waiting", 0) or 0
        except Exception:
            waiting = 0
        if waiting <= 0:
            time.sleep(0.02)
            continue
        try:
            line = ser.readline()
        except Exception:
            return
        if not line:
            continue
        try:
            text = line.decode("utf-8", errors="replace").strip()
        except Exception:
            text = str(line)
        if text:
            print(f"[arduino] {text}")


def open_serial(port: str, baud: int, timeout_s: float):
    serial, _ = _import_serial()
    ser = serial.Serial(port=port, baudrate=baud, timeout=timeout_s)
    try:
        ser.reset_input_buffer()
    except Exception:
        pass
    time.sleep(1.8)
    read_for(ser, 0.6)
    return ser


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Envia comandos numéricos para o Arduino (hand_servo_control).")
    p.add_argument("--port", default="auto", help='Porta serial (ex: COM5). Use "auto" para detectar.')
    p.add_argument("--baud", type=int, default=9600, help="Baud rate (default: 9600).")
    p.add_argument("--timeout", type=float, default=0.2, help="Timeout de leitura (segundos).")
    p.add_argument("--cmd", default=None, help="Envia um comando (ex: 7) e sai.")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    port = args.port
    if port == "auto":
        port = pick_auto_port() or ""
    if not port:
        print("Nenhuma porta serial encontrada. Conecte o Arduino via USB e tente novamente.")
        return 2

    print(f"Abrindo porta {port} @ {args.baud} ...")
    try:
        ser = open_serial(port=port, baud=args.baud, timeout_s=args.timeout)
    except Exception as e:
        print(f"Falha ao abrir {port}: {type(e).__name__}: {e}")
        return 3

    try:
        if args.cmd is not None:
            cmd = str(args.cmd).strip()
            ser.write((cmd + "\n").encode("utf-8"))
            read_for(ser, 1.2)
            return 0

        print_menu()
        while True:
            raw = input("> ").strip()
            if not raw:
                continue
            if raw.lower() in {"q", "quit", "exit"}:
                return 0
            if raw.lower() in {"ports", "port"}:
                ports = list_serial_ports()
                if not ports:
                    print("Nenhuma porta encontrada.")
                else:
                    for p in ports:
                        dev = p.get("device")
                        desc = p.get("description") or ""
                        print(f"- {dev}: {desc}".strip())
                continue

            try:
                n = int(raw)
            except Exception:
                print("Entrada inválida. Digite um número (1..11), 'ports' ou 'q'.")
                continue

            ser.write((str(n) + "\n").encode("utf-8"))
            read_for(ser, 0.8)

    except KeyboardInterrupt:
        print("\nEncerrando...")
        return 0
    finally:
        try:
            ser.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
