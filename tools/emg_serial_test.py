from __future__ import annotations

import argparse
import sys
import time


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Teste rápido: lê linhas da serial e imprime no terminal.")
    p.add_argument("--port", required=True, help="Porta (ex: COM7)")
    p.add_argument("--baud", type=int, default=115200, help="Baud (default: 115200)")
    p.add_argument("--seconds", type=float, default=5.0, help="Duração do teste (segundos)")
    args = p.parse_args(argv)

    try:
        import serial
    except Exception as e:  # noqa: BLE001
        print(f"pyserial não instalado: {type(e).__name__}: {e}")
        print("Instale com: pip install pyserial")
        return 2

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.5)
    except Exception as e:  # noqa: BLE001
        print(f"Falha ao abrir {args.port}: {type(e).__name__}: {e}")
        return 3

    deadline = time.time() + float(args.seconds)
    count = 0
    try:
        ser.reset_input_buffer()
    except Exception:
        pass

    try:
        while time.time() < deadline:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            print(line)
            count += 1
    finally:
        try:
            ser.close()
        except Exception:
            pass

    if count == 0:
        print("NENHUMA LINHA RECEBIDA. Verifique se o Arduino está enviando Serial.println(...) e se o baud está correto.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

