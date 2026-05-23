from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class EmgProcessingConfig:
    sample_rate_hz: float = 1000.0
    highpass_hz: float = 20.0
    lowpass_hz: float = 450.0
    notch_hz: float | None = 60.0
    notch_q: float = 30.0
    envelope_lowpass_hz: float = 5.0
    backend: str = "lite"


class SosIirFilter:
    def __init__(self, signal_module, sos: np.ndarray):
        self._signal = signal_module
        self._sos = sos
        self._zi = self._signal.sosfilt_zi(sos)

    def reset(self) -> None:
        self._zi = self._signal.sosfilt_zi(self._sos)

    def step(self, x: float) -> float:
        y, self._zi = self._signal.sosfilt(
            self._sos, np.array([x], dtype=np.float64), zi=self._zi
        )
        return float(y[0])


class LiteEmgProcessor:
    def __init__(self, cfg: EmgProcessingConfig):
        self.cfg = cfg
        self._dc = 0.0
        self._env = 0.0

    def reset(self) -> None:
        self._dc = 0.0
        self._env = 0.0

    def calibrate(self, raw: float) -> None:
        self._dc = float(raw)
        self._env = 0.0

    def step(self, raw: float, dt_s: float | None = None) -> tuple[float, float]:
        x = float(raw)

        if dt_s is None or dt_s <= 0:
            fs = max(1.0, float(self.cfg.sample_rate_hz))
            dt_s = 1.0 / fs

        dt_s = float(min(1.0, max(1e-4, dt_s)))

        hp_fc = float(max(0.1, self.cfg.highpass_hz))
        hp_rc = 1.0 / (2.0 * np.pi * hp_fc)
        dc_alpha = dt_s / (hp_rc + dt_s)

        env_fc = float(max(0.1, self.cfg.envelope_lowpass_hz))
        env_rc = 1.0 / (2.0 * np.pi * env_fc)
        env_alpha = dt_s / (env_rc + dt_s)

        self._dc += dc_alpha * (x - self._dc)
        hp = x - self._dc
        self._env += env_alpha * (abs(hp) - self._env)
        return hp, self._env


class ScipyEmgProcessor:
    def __init__(self, cfg: EmgProcessingConfig):
        self.cfg = cfg

        try:
            from scipy import signal
        except KeyboardInterrupt as e:
            raise RuntimeError("Importação do SciPy interrompida (aguarde carregar ou use backend=lite).") from e
        except Exception as e:
            raise RuntimeError("SciPy indisponível. Instale scipy ou use backend=lite.") from e

        nyq = 0.5 * cfg.sample_rate_hz
        hp = max(0.1, cfg.highpass_hz) / nyq
        lp = min(nyq - 1.0, cfg.lowpass_hz) / nyq
        if lp <= hp:
            lp = min(0.99, hp + 0.1)

        sos_bp = signal.butter(4, [hp, lp], btype="bandpass", output="sos")
        self._bp = SosIirFilter(signal, sos_bp)

        self._notch: SosIirFilter | None = None
        if cfg.notch_hz is not None and cfg.notch_hz > 0:
            w0 = cfg.notch_hz / nyq
            b, a = signal.iirnotch(w0=w0, Q=cfg.notch_q)
            sos = signal.tf2sos(b, a)
            self._notch = SosIirFilter(signal, sos)

        env_lp = max(0.1, cfg.envelope_lowpass_hz) / nyq
        sos_env = signal.butter(2, env_lp, btype="lowpass", output="sos")
        self._env = SosIirFilter(signal, sos_env)

    def reset(self) -> None:
        self._bp.reset()
        if self._notch is not None:
            self._notch.reset()
        self._env.reset()

    def calibrate(self, raw: float) -> None:
        self.reset()

    def step(self, raw: float, dt_s: float | None = None) -> tuple[float, float]:
        x = self._bp.step(raw)
        if self._notch is not None:
            x = self._notch.step(x)
        env = self._env.step(abs(x))
        return x, env


class EmgProcessor:
    def __init__(self, cfg: EmgProcessingConfig):
        self.cfg = cfg
        backend = (cfg.backend or "lite").lower().strip()
        if backend == "scipy":
            self._impl = ScipyEmgProcessor(cfg)
        else:
            self._impl = LiteEmgProcessor(cfg)

    def reset(self) -> None:
        self._impl.reset()

    def calibrate(self, raw: float) -> None:
        if hasattr(self._impl, "calibrate"):
            self._impl.calibrate(raw)

    def step(self, raw: float, dt_s: float | None = None) -> tuple[float, float]:
        return self._impl.step(raw, dt_s=dt_s)
