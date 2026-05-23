from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class EmgInterpretation:
    state: str
    activation: float
    note: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"state": self.state, "activation": float(self.activation)}
        if self.note:
            d["note"] = str(self.note)
        return d


def interpret_emg(
    *,
    rms: float,
    mav: float,
    zero_crossings: float,
    mean_freq_hz: float,
    peak_freq_hz: float,
    calibration: Optional[dict[str, float]],
) -> EmgInterpretation:
    noise = 1.0
    if calibration and "noise_filtered_std" in calibration:
        try:
            noise = float(calibration.get("noise_filtered_std") or 1.0)
        except Exception:
            noise = 1.0
    if noise <= 1e-9:
        noise = 1.0

    activation = float(rms) / float(noise)

    if activation < 3.0 and float(mav) < float(noise) * 2.0:
        st = "repouso"
    elif activation < 10.0:
        st = "contracao_leve"
    else:
        st = "contracao_forte"

    note = None
    if st == "repouso":
        if float(activation) >= 2.0 and (float(zero_crossings) > 25.0 or float(mean_freq_hz) > 120.0 or float(peak_freq_hz) > 160.0):
            note = "ruido_em_repouso"

    if st != "repouso":
        if float(mean_freq_hz) < 10.0 and float(peak_freq_hz) < 10.0:
            note = note or "sinal_fraco_ou_instavel"

    return EmgInterpretation(state=st, activation=float(activation), note=note)

