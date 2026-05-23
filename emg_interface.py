from __future__ import annotations

import sys
from multiprocessing import freeze_support

from project.emg_interface import main


def _configure_utf8_stdout() -> None:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    _configure_utf8_stdout()
    freeze_support()
    raise SystemExit(main())

