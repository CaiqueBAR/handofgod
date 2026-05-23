from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FeatureVector:
    rms: float
    mav: float
    variance: float
    energy: float
    waveform_length: float
    zero_crossings: float
    mean_freq_hz: float
    median_freq_hz: float
    peak_freq_hz: float

    def to_array(self) -> np.ndarray:
        return np.array(
            [
                self.rms,
                self.mav,
                self.variance,
                self.energy,
                self.waveform_length,
                self.zero_crossings,
                self.mean_freq_hz,
                self.median_freq_hz,
                self.peak_freq_hz,
            ],
            dtype=np.float64,
        )

    @staticmethod
    def feature_names() -> list[str]:
        return [
            "rms",
            "mav",
            "variance",
            "energy",
            "waveform_length",
            "zero_crossings",
            "mean_freq_hz",
            "median_freq_hz",
            "peak_freq_hz",
        ]


def _safe_float(x: float) -> float:
    if not np.isfinite(x):
        return 0.0
    return float(x)


def compute_features(x: np.ndarray, fs_hz: float, zc_threshold: float = 0.01) -> FeatureVector:
    """
    x: janela do sinal EMG (preferencialmente já filtrado em banda), shape (N,)
    fs_hz: frequência de amostragem
    """
    if x.ndim != 1:
        x = x.reshape(-1)
    n = int(x.shape[0])
    if n < 8:
        return FeatureVector(*(0.0 for _ in range(9)))

    x = x.astype(np.float64, copy=False)
    mav = np.mean(np.abs(x))
    rms = np.sqrt(np.mean(x * x))
    var = np.var(x, ddof=0)
    energy = np.sum(x * x)
    wl = np.sum(np.abs(np.diff(x)))

    s1 = x[:-1]
    s2 = x[1:]
    zc = np.sum(((s1 * s2) < 0) & (np.abs(s1 - s2) >= zc_threshold))

    window = np.hanning(n)
    xf = np.fft.rfft(x * window)
    psd = (np.abs(xf) ** 2) / max(1.0, np.sum(window * window))
    freqs = np.fft.rfftfreq(n, d=1.0 / fs_hz)

    psd_sum = float(np.sum(psd))
    if psd_sum <= 0.0:
        mean_f = 0.0
        median_f = 0.0
        peak_f = 0.0
    else:
        mean_f = float(np.sum(freqs * psd) / psd_sum)
        cdf = np.cumsum(psd) / psd_sum
        median_f = float(freqs[int(np.searchsorted(cdf, 0.5))])
        peak_f = float(freqs[int(np.argmax(psd))])

    return FeatureVector(
        rms=_safe_float(rms),
        mav=_safe_float(mav),
        variance=_safe_float(var),
        energy=_safe_float(energy),
        waveform_length=_safe_float(wl),
        zero_crossings=_safe_float(float(zc)),
        mean_freq_hz=_safe_float(mean_f),
        median_freq_hz=_safe_float(median_f),
        peak_freq_hz=_safe_float(peak_f),
    )

