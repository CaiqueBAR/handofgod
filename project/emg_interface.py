from __future__ import annotations

import argparse
import csv
import json
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Deque, Optional
from urllib.parse import parse_qs, urlparse

import numpy as np

try:
    from .feature_extraction import FeatureVector, compute_features
    from .emg_interpretation import interpret_emg
    from .servo_controller import DEFAULT_LABEL_TO_COMMAND, ServoSerialController
    from .signal_capture import SerialSignalCapture
    from .signal_processing import EmgProcessingConfig, EmgProcessor
    from .utils import list_serial_ports
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from project.feature_extraction import FeatureVector, compute_features
    from project.emg_interpretation import interpret_emg
    from project.servo_controller import DEFAULT_LABEL_TO_COMMAND, ServoSerialController
    from project.signal_capture import SerialSignalCapture
    from project.signal_processing import EmgProcessingConfig, EmgProcessor
    from project.utils import list_serial_ports


@dataclass(frozen=True)
class EmgStatus:
    t: float
    raw: float
    filtered: float
    envelope: float
    features: dict[str, float] | None
    interpretation: dict | None
    prediction: dict | None
    servo_command: str | None
    recording: bool
    label: str | None


class SharedState:
    def __init__(self, maxlen: int):
        self._lock = threading.Lock()
        self._samples: Deque[EmgStatus] = deque(maxlen=maxlen)
        self._latest: Optional[EmgStatus] = None
        self._listeners: list[deque[str]] = []
        self._status_listeners: list[deque[EmgStatus]] = []

        self.recording = False
        self.active_label: Optional[str] = None
        self.predict_enabled = False
        self.servo_enabled = False

        self._calibration_request_s: Optional[float] = None
        self.calibration: Optional[dict[str, float]] = None

    def append(self, status: EmgStatus) -> None:
        payload = json.dumps(asdict(status), ensure_ascii=False)
        with self._lock:
            self._samples.append(status)
            self._latest = status
            for q in list(self._listeners):
                if len(q) >= 512:
                    q.popleft()
                q.append(payload)
            for q in list(self._status_listeners):
                if len(q) >= 4096:
                    q.popleft()
                q.append(status)

    def latest(self) -> Optional[EmgStatus]:
        with self._lock:
            return self._latest

    def snapshot(self) -> list[EmgStatus]:
        with self._lock:
            return list(self._samples)

    def add_listener(self) -> deque[str]:
        q: deque[str] = deque()
        with self._lock:
            self._listeners.append(q)
        return q

    def remove_listener(self, q: deque[str]) -> None:
        with self._lock:
            if q in self._listeners:
                self._listeners.remove(q)

    def add_status_listener(self) -> deque[EmgStatus]:
        q: deque[EmgStatus] = deque()
        with self._lock:
            self._status_listeners.append(q)
        return q

    def remove_status_listener(self, q: deque[EmgStatus]) -> None:
        with self._lock:
            if q in self._status_listeners:
                self._status_listeners.remove(q)

    def request_calibration(self, seconds: float = 2.0) -> None:
        with self._lock:
            self._calibration_request_s = float(max(0.1, seconds))

    def pop_calibration_request(self) -> Optional[float]:
        with self._lock:
            v = self._calibration_request_s
            self._calibration_request_s = None
            return v

    def set_calibration(self, cal: dict[str, float]) -> None:
        with self._lock:
            self.calibration = dict(cal)


class CsvFeatureLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        self._writer: Optional[csv.DictWriter] = None
        self._fh = self.path.open("a", newline="", encoding="utf-8")

        self._ensure_header()

    def _ensure_header(self) -> None:
        feature_names = FeatureVector.feature_names()
        fieldnames = ["t", "label", *feature_names]
        self._writer = csv.DictWriter(self._fh, fieldnames=fieldnames)
        if self.path.stat().st_size == 0:
            self._writer.writeheader()
            self._fh.flush()

    def log(self, t: float, label: str, fv: FeatureVector) -> None:
        row = {"t": f"{t:.6f}", "label": label}
        for name, value in zip(FeatureVector.feature_names(), fv.to_array().tolist()):
            row[name] = f"{float(value):.10g}"
        with self._lock:
            assert self._writer is not None
            self._writer.writerow(row)
            self._fh.flush()

    def close(self) -> None:
        with self._lock:
            try:
                self._fh.close()
            except Exception:
                pass


class CsvRuntimeLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        self._writer: Optional[csv.DictWriter] = None
        self._fh = self.path.open("a", newline="", encoding="utf-8")
        self._ensure_header()

    def _ensure_header(self) -> None:
        feature_names = FeatureVector.feature_names()
        fieldnames = [
            "t",
            "raw",
            "filtered",
            "envelope",
            "recording",
            "label",
            "pred_label",
            "pred_confidence",
            "servo_command",
            *feature_names,
        ]
        self._writer = csv.DictWriter(self._fh, fieldnames=fieldnames)
        if self.path.stat().st_size == 0:
            self._writer.writeheader()
            self._fh.flush()

    def log(self, status: EmgStatus) -> None:
        row = {
            "t": f"{status.t:.6f}",
            "raw": f"{status.raw:.10g}",
            "filtered": f"{status.filtered:.10g}",
            "envelope": f"{status.envelope:.10g}",
            "recording": "1" if status.recording else "0",
            "label": status.label or "",
            "pred_label": (status.prediction or {}).get("label", "") if status.prediction else "",
            "pred_confidence": f"{float((status.prediction or {}).get('confidence') or 0.0):.6f}"
            if status.prediction
            else "",
            "servo_command": status.servo_command or "",
        }
        if status.features:
            for k, v in status.features.items():
                row[k] = f"{float(v):.10g}"
        with self._lock:
            assert self._writer is not None
            self._writer.writerow(row)
            self._fh.flush()

    def close(self) -> None:
        with self._lock:
            try:
                self._fh.close()
            except Exception:
                pass


class ApiHandler(BaseHTTPRequestHandler):
    state: SharedState
    capture: SerialSignalCapture
    servo: Optional[ServoSerialController]

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, obj, status: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._send_json({"ok": True})
            return

        if parsed.path == "/ports":
            self._send_json([p.__dict__ for p in list_serial_ports()])
            return

        if parsed.path == "/latest":
            s = self.state.latest()
            self._send_json(asdict(s) if s else None)
            return

        if parsed.path == "/history":
            self._send_json([asdict(s) for s in self.state.snapshot()])
            return

        if parsed.path == "/stream":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            q = self.state.add_listener()
            try:
                while True:
                    if q:
                        payload = q.popleft()
                        msg = f"event: emg\ndata: {payload}\n\n".encode("utf-8")
                        self.wfile.write(msg)
                        self.wfile.flush()
                    else:
                        time.sleep(0.05)
            except Exception:
                return
            finally:
                self.state.remove_listener(q)

        if parsed.path == "/set_label":
            qs = parse_qs(parsed.query)
            label = (qs.get("label") or [None])[0]
            if not label:
                self._send_json({"ok": False, "error": "missing_label"}, status=400)
                return
            self.state.active_label = str(label)
            self._send_json({"ok": True, "label": self.state.active_label})
            return

        if parsed.path == "/recording":
            qs = parse_qs(parsed.query)
            on = (qs.get("on") or [None])[0]
            if on is None:
                self._send_json({"ok": False, "error": "missing_on"}, status=400)
                return
            self.state.recording = on in ("1", "true", "True", "on", "yes")
            self._send_json({"ok": True, "recording": self.state.recording})
            return

        if parsed.path == "/servo":
            qs = parse_qs(parsed.query)
            on = (qs.get("on") or [None])[0]
            if on is None:
                self._send_json({"ok": False, "error": "missing_on"}, status=400)
                return
            self.state.servo_enabled = on in ("1", "true", "True", "on", "yes")
            self._send_json({"ok": True, "servo_enabled": self.state.servo_enabled})
            return

        if parsed.path == "/config":
            qs = parse_qs(parsed.query)
            key = (qs.get("key") or [None])[0]
            value = (qs.get("value") or [None])[0]
            if not key or value is None:
                self._send_json({"ok": False, "error": "missing_key_or_value"}, status=400)
                return
            line = f"{key}={value}"
            self.capture.write_line(line)
            self._send_json({"ok": True, "sent": line})
            return

        self._send_json({"ok": False, "error": "not_found"}, status=404)


def run_http_server(
    host: str,
    port: int,
    state: SharedState,
    capture: SerialSignalCapture,
    servo: Optional[ServoSerialController],
) -> ThreadingHTTPServer:
    ApiHandler.state = state
    ApiHandler.capture = capture
    ApiHandler.servo = servo
    server = ThreadingHTTPServer((host, port), ApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _prediction_to_dict(pred: Optional[Any]) -> Optional[dict]:
    if pred is None:
        return None
    try:
        return {"label": pred.label, "confidence": pred.confidence, "probabilities": pred.probabilities}
    except Exception:
        return None


def run_emg_loop(
    capture: SerialSignalCapture,
    processor: EmgProcessor,
    state: SharedState,
    model_path: Path,
    label_to_command: dict[str, str],
    servo: Optional[ServoSerialController],
    window_s: float,
    step_s: float,
    plot_mode: str,
    emg_source: str,
    arduino_alpha: float,
    stop_event: threading.Event,
    dataset_path: Path,
) -> None:
    x_buf: Deque[tuple[float, float]] = deque()
    last_t: Optional[float] = None
    next_step_t: Optional[float] = None
    fs_est = float(max(1.0, processor.cfg.sample_rate_hz))
    fs_alpha = 0.05
    calibrated = False
    last_arduino_filtered: Optional[float] = None
    cal_active = False
    cal_deadline_t: Optional[float] = None
    cal_raw: list[float] = []
    cal_filt: list[float] = []
    cal_baseline_raw = 0.0
    cal_baseline_filt = 0.0
    cal_noise_filt = 1.0

    logger: Optional[CsvFeatureLogger] = None
    runtime_logger: Optional[CsvRuntimeLogger] = None

    classifier: Optional[Any] = None
    last_model_mtime = 0.0

    keep_s = max(float(window_s) * 4.0, 2.0)
    last_interp: Optional[dict] = None

    while not stop_event.is_set():
        try:
            for s in capture.samples():
                if stop_event.is_set():
                    break

                dt_s: Optional[float] = None
                if last_t is not None:
                    dt_s = float(s.t - last_t)
                    if dt_s > 0:
                        inst_fs = 1.0 / dt_s
                        fs_est += fs_alpha * (inst_fs - fs_est)
                last_t = s.t

                input_value = float(s.raw)
                if emg_source == "filtered":
                    if s.filtered is not None:
                        input_value = float(s.filtered)
                elif emg_source == "auto":
                    if s.filtered is not None:
                        input_value = float(s.filtered)

                effective_mode = plot_mode
                if effective_mode == "auto":
                    effective_mode = "arduino" if s.filtered is not None else "processed"

                if effective_mode == "arduino":
                    raw_value = float(s.raw)
                    if s.filtered is not None:
                        filtered_value = float(s.filtered)
                        last_arduino_filtered = filtered_value
                    else:
                        if last_arduino_filtered is None:
                            last_arduino_filtered = raw_value
                        last_arduino_filtered = (float(arduino_alpha) * raw_value) + (
                            (1.0 - float(arduino_alpha)) * float(last_arduino_filtered)
                        )
                        filtered_value = float(last_arduino_filtered)
                    filtered = float(filtered_value)
                    x_buf.append((s.t, float(filtered_value)))
                else:
                    if not calibrated:
                        processor.calibrate(float(input_value))
                        calibrated = True

                    filtered, envelope = processor.step(float(input_value), dt_s=dt_s)
                    x_buf.append((s.t, float(filtered)))

                cutoff_keep = float(s.t) - float(keep_s)
                while x_buf and float(x_buf[0][0]) < cutoff_keep:
                    x_buf.popleft()

                req = state.pop_calibration_request()
                if req is not None:
                    cal_active = True
                    cal_deadline_t = float(s.t + float(req))
                    cal_raw = []
                    cal_filt = []

                if cal_active:
                    cal_raw.append(float(s.raw))
                    if effective_mode == "arduino":
                        cal_filt.append(float(filtered))
                    else:
                        cal_filt.append(float(filtered))
                    if cal_deadline_t is not None and float(s.t) >= float(cal_deadline_t) and len(cal_filt) >= 50:
                        raw_arr = np.asarray(cal_raw, dtype=np.float64)
                        filt_arr = np.asarray(cal_filt, dtype=np.float64)
                        cal_baseline_raw = float(np.mean(raw_arr))
                        cal_baseline_filt = float(np.mean(filt_arr))
                        cal_noise_filt = float(np.std(filt_arr - cal_baseline_filt))
                        if not np.isfinite(cal_noise_filt) or cal_noise_filt <= 1e-9:
                            cal_noise_filt = 1.0
                        state.set_calibration(
                            {
                                "baseline_raw": float(cal_baseline_raw),
                                "baseline_filtered": float(cal_baseline_filt),
                                "noise_filtered_std": float(cal_noise_filt),
                            }
                        )
                        cal_active = False
                        cal_deadline_t = None
                        cal_raw = []
                        cal_filt = []

                if effective_mode == "arduino":
                    envelope = abs(float(filtered) - float(cal_baseline_filt))
                envelope = float(envelope)

                fv: Optional[FeatureVector] = None
                pred: Optional[Any] = None
                cmd: Optional[str] = None

                if next_step_t is None:
                    next_step_t = s.t + float(step_s)

                if s.t >= next_step_t:
                    next_step_t = s.t + float(step_s)

                    cutoff = s.t - float(window_s)
                    win = [v for (t, v) in x_buf if t >= cutoff]
                    if len(win) >= 32:
                        fs_win = float(len(win)) / float(window_s) if window_s > 0 else fs_est
                        x_win = np.asarray(win, dtype=np.float64)
                        if effective_mode == "arduino":
                            x_win = (x_win - float(cal_baseline_filt)) / 1023.0
                        fv = compute_features(x_win, fs_hz=fs_win, zc_threshold=0.02)
                        try:
                            interp = interpret_emg(
                                rms=float(fv.rms),
                                mav=float(fv.mav),
                                zero_crossings=float(fv.zero_crossings),
                                mean_freq_hz=float(fv.mean_freq_hz),
                                peak_freq_hz=float(fv.peak_freq_hz),
                                calibration=state.calibration,
                            )
                            last_interp = interp.to_dict()
                        except Exception:
                            last_interp = None

                    if state.recording and state.active_label and fv is not None:
                        if logger is None:
                            logger = CsvFeatureLogger(dataset_path)
                        logger.log(t=s.t, label=state.active_label, fv=fv)
                        if runtime_logger is None:
                            runtime_logger = CsvRuntimeLogger(dataset_path.with_name("runtime_log.csv"))

                    if state.predict_enabled:
                        try:
                            if model_path.exists():
                                if classifier is None:
                                    try:
                                        from .model_predict import EmgClassifier as _EmgClassifier
                                    except Exception:
                                        from project.model_predict import EmgClassifier as _EmgClassifier
                                    classifier = _EmgClassifier.load(model_path)
                                    last_model_mtime = model_path.stat().st_mtime
                                else:
                                    mtime = model_path.stat().st_mtime
                                    if mtime != last_model_mtime:
                                        try:
                                            from .model_predict import EmgClassifier as _EmgClassifier
                                        except Exception:
                                            from project.model_predict import EmgClassifier as _EmgClassifier
                                        classifier = _EmgClassifier.load(model_path)
                                        last_model_mtime = mtime
                        except Exception:
                            classifier = None

                        if classifier is not None and fv is not None:
                            pred = classifier.predict(fv)
                            if pred is not None and state.servo_enabled and servo is not None:
                                cmd = label_to_command.get(pred.label)
                                if cmd:
                                    try:
                                        servo.send(cmd)
                                    except Exception:
                                        pass

                status = EmgStatus(
                    t=s.t,
                    raw=float(s.raw),
                    filtered=float(filtered),
                    envelope=float(envelope),
                    features={k: float(v) for k, v in zip(FeatureVector.feature_names(), fv.to_array())}
                    if fv is not None
                    else None,
                    interpretation=last_interp,
                    prediction=_prediction_to_dict(pred),
                    servo_command=cmd,
                    recording=bool(state.recording),
                    label=state.active_label,
                )
                state.append(status)
                if runtime_logger is not None and fv is not None and state.recording:
                    runtime_logger.log(status)

        except Exception:
            try:
                capture.close()
            except Exception:
                pass
            time.sleep(1.0)
            try:
                capture.open()
            except Exception:
                time.sleep(2.0)

    if logger is not None:
        logger.close()
    if runtime_logger is not None:
        runtime_logger.close()


def run_gui(state: SharedState, window_seconds: float, plot_mode: str, y_max: float, y_ticks: list[float]) -> None:
    import sys

    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    fig, ax = plt.subplots(1, 1)
    fig.canvas.manager.set_window_title("Interface EMG")

    (raw_line,) = ax.plot([], [], label="raw")
    (filt_line,) = ax.plot([], [], label="filtrado")
    (env_line,) = ax.plot([], [], label="envelope")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_ylabel("Amplitude")
    ax.set_xlabel("Tempo (s)")

    t_buf: Deque[float] = deque()
    raw_buf: Deque[float] = deque()
    filt_buf: Deque[float] = deque()
    env_buf: Deque[float] = deque()

    status_text = fig.text(0.02, 0.98, "", va="top")
    help_text = fig.text(
        0.02,
        0.94,
        "Atalhos: [r]=gravar  [1..4]=rótulo  [0]=limpar rótulo  [p]=predição  [s]=servo",
        va="top",
        fontsize=9,
    )

    ax.set_xlim(-window_seconds, 0)
    ax.set_ylim(0, float(y_max))
    ax.set_yticks([float(v) for v in y_ticks])

    def refresh(_):
        samples = state.snapshot()
        if not samples:
            return (raw_line, filt_line, env_line)

        latest_t = samples[-1].t
        cutoff = latest_t - window_seconds

        t_buf.clear()
        raw_buf.clear()
        filt_buf.clear()
        env_buf.clear()

        last_label = None
        last_pred = None
        last_conf = 0.0
        last_cmd = None
        recording = False
        last_peak_hz: Optional[float] = None
        last_mean_hz: Optional[float] = None

        for s in samples:
            if s.t < cutoff:
                continue
            t_buf.append(s.t - latest_t)
            raw_buf.append(float(s.raw))
            filt_buf.append(float(s.filtered))
            env_buf.append(float(s.envelope))
            if s.prediction:
                last_pred = s.prediction.get("label")
                last_conf = float(s.prediction.get("confidence") or 0.0)
            if s.features:
                try:
                    last_peak_hz = float(s.features.get("peak_freq_hz")) if "peak_freq_hz" in s.features else last_peak_hz
                    last_mean_hz = float(s.features.get("mean_freq_hz")) if "mean_freq_hz" in s.features else last_mean_hz
                except Exception:
                    pass
            last_label = s.label
            last_cmd = s.servo_command or last_cmd
            recording = s.recording

        xs = list(t_buf)
        raw_line.set_data(xs, list(raw_buf))
        filt_line.set_data(xs, list(filt_buf))
        env_line.set_data(xs, list(env_buf))

        effective_mode = plot_mode
        if effective_mode == "auto":
            effective_mode = "arduino" if raw_buf and filt_buf else "processed"

        raw_line.set_visible(effective_mode == "arduino")
        filt_line.set_visible(effective_mode == "arduino")
        env_line.set_visible(effective_mode != "arduino")

        if xs:
            ax.set_xlim(-window_seconds, 0)

        freq_txt = "-"
        if last_peak_hz is not None:
            if last_mean_hz is not None:
                freq_txt = f"pico={last_peak_hz:.1f}Hz média={last_mean_hz:.1f}Hz"
            else:
                freq_txt = f"pico={last_peak_hz:.1f}Hz"

        status_text.set_text(
            f"raw={raw_buf[-1]:.0f} filtrado={filt_buf[-1]:.1f} amp={env_buf[-1]:.1f} "
            f"freq={freq_txt} gravando={recording} rótulo={last_label or '-'} "
            f"predição={state.predict_enabled} servo={state.servo_enabled} predito={last_pred or '-'} "
            f"confiança={last_conf:.2f} comando={last_cmd or '-'}"
        )

        return (raw_line, filt_line, env_line)

    def on_key(event):
        if event.key == "r":
            state.recording = not state.recording
        elif event.key in ("1", "2", "3", "4"):
            labels = ["mao_aberta", "mao_fechada", "flexao", "extensao"]
            idx = int(event.key) - 1
            state.active_label = labels[idx]
        elif event.key == "0":
            state.active_label = None
        elif event.key == "p":
            state.predict_enabled = not state.predict_enabled
        elif event.key == "s":
            state.servo_enabled = not state.servo_enabled

    fig.canvas.mpl_connect("key_press_event", on_key)

    anim = FuncAnimation(fig, refresh, interval=33, blit=False, cache_frame_data=False)
    setattr(fig, "_anim", anim)
    try:
        plt.show()
    except KeyboardInterrupt:
        pass


def train_from_latest_dataset(dataset_path: Path, model_path: Path) -> str:
    try:
        from .model_training import load_feature_dataset, save_model, train_model
    except Exception:
        from project.model_training import load_feature_dataset, save_model, train_model
    x, y = load_feature_dataset(dataset_path)
    model, report = train_model(x, y)
    save_model(model, model_path)
    return report


def main() -> None:
    import sys

    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        prog="emg_interface",
        description="Interface EMG em tempo real (captura, filtro, features, ML, API e controle de servo).",
    )
    parser.add_argument("--emg-port", default="auto", help="Porta do EMG (ex: COM3). Use 'auto' para autodetectar.")
    parser.add_argument("--emg-baud", type=int, default=115200, help="Baud rate da serial do EMG.")
    parser.add_argument("--port", dest="port", default=None, help="Alias de --emg-port.")
    parser.add_argument("--baud", dest="baud", type=int, default=None, help="Alias de --emg-baud.")
    parser.add_argument("--list-ports", action="store_true", help="Lista portas seriais disponíveis (JSON).")
    parser.add_argument("--timeout", type=float, default=1.0, help="Timeout de leitura da serial (segundos).")
    parser.add_argument(
        "--open-timeout",
        type=float,
        default=6.0,
        help="Timeout máximo para tentar abrir uma porta serial (segundos).",
    )
    parser.add_argument("--dtr", choices=["on", "off", "keep"], default="keep", help="Configura DTR ao abrir a porta.")
    parser.add_argument("--rts", choices=["on", "off", "keep"], default="keep", help="Configura RTS ao abrir a porta.")
    parser.add_argument("--open-retries", type=int, default=3, help="Tentativas de abertura por porta.")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="Atraso entre tentativas (segundos).")
    parser.add_argument("--servo-port", default=None, help="Porta do controlador de servos (ex: COM5).")
    parser.add_argument("--servo-baud", type=int, default=115200, help="Baud rate da serial do servo.")
    parser.add_argument("--http", action="store_true", help="Ativa o servidor HTTP (API).")
    parser.add_argument("--http-host", default="127.0.0.1", help="Host do servidor HTTP.")
    parser.add_argument("--http-port", type=int, default=8000, help="Porta do servidor HTTP.")
    parser.add_argument("--sample-rate-hz", type=float, default=1000.0, help="Taxa de amostragem estimada (Hz).")
    parser.add_argument(
        "--backend",
        choices=["lite", "scipy"],
        default="lite",
        help="Backend de filtros. 'lite' é mais leve; 'scipy' usa filtros IIR (SciPy).",
    )
    parser.add_argument("--window-s", type=float, default=0.250, help="Janela de features (segundos).")
    parser.add_argument("--step-s", type=float, default=0.050, help="Passo entre janelas de features (segundos).")
    parser.add_argument(
        "--plot-mode",
        choices=["auto", "arduino", "processed"],
        default="auto",
        help="Modo do gráfico. 'arduino' replica o Serial Plotter (raw + filtrado). 'processed' mostra envelope/processado.",
    )
    parser.add_argument(
        "--emg-source",
        choices=["auto", "raw", "filtered"],
        default="auto",
        help="Qual coluna usar como sinal de entrada (quando o Arduino envia 1 ou 2 valores por linha).",
    )
    parser.add_argument(
        "--arduino-alpha",
        type=float,
        default=0.2,
        help="Alpha do filtro EMA no modo 'arduino' (usado quando a linha tem só 1 valor).",
    )
    parser.add_argument("--y-max", type=float, default=400.0, help="Limite superior do eixo Y do gráfico.")
    parser.add_argument(
        "--y-ticks",
        default="0,100,200,300,400",
        help="Marcas do eixo Y separadas por vírgula (ex: 0,100,200,300,400).",
    )
    parser.add_argument(
        "--model",
        default=str(Path("project") / "models" / "emg_model.joblib"),
        help="Caminho do modelo treinado (joblib).",
    )
    parser.add_argument(
        "--dataset",
        default=str(Path("project") / "datasets" / "emg_features.csv"),
        help="Caminho do CSV de features (para treino).",
    )
    parser.add_argument(
        "--ui",
        choices=["qt", "mpl"],
        default="qt",
        help="Interface gráfica. 'qt' replica o layout estilo Serial Plotter. 'mpl' usa matplotlib (legado).",
    )
    parser.add_argument("--no-gui", action="store_true", help="Executa sem interface gráfica (somente API).")
    args = parser.parse_args()

    if args.list_ports:
        print(json.dumps([p.__dict__ for p in list_serial_ports()], ensure_ascii=False, indent=2))
        return

    if args.port is not None:
        args.emg_port = args.port
    if args.baud is not None:
        args.emg_baud = args.baud

    dtr = None if args.dtr == "keep" else args.dtr == "on"
    rts = None if args.rts == "keep" else args.rts == "on"

    state = SharedState(maxlen=max(2000, int(args.sample_rate_hz * 15)))

    capture = SerialSignalCapture(
        port=args.emg_port,
        baud=args.emg_baud,
        timeout_s=float(args.timeout),
        open_timeout_s=float(args.open_timeout),
        dtr=dtr,
        rts=rts,
        open_retries=int(args.open_retries),
        retry_delay_s=float(args.retry_delay),
    )

    servo: Optional[ServoSerialController] = None
    if args.servo_port is not None:
        servo = ServoSerialController(port=args.servo_port, baud=args.servo_baud)
        try:
            servo.open()
        except Exception:
            servo = None
        if servo is not None:
            print(f"Servo conectado em {servo._port} @ {args.servo_baud} baud", flush=True)

    cfg = EmgProcessingConfig(sample_rate_hz=float(args.sample_rate_hz), backend=str(args.backend))
    processor = EmgProcessor(cfg)

    model_path = Path(args.model)
    dataset_path = Path(args.dataset)

    server: Optional[ThreadingHTTPServer] = None
    if bool(args.http):
        server = run_http_server(args.http_host, args.http_port, state, capture, servo)
        print(f"API HTTP em http://{args.http_host}:{args.http_port}", flush=True)

    if not args.no_gui and str(args.ui) == "qt":
        try:
            try:
                from .qt_emg_plotter import run_qt_plotter
            except Exception:
                from project.qt_emg_plotter import run_qt_plotter

            run_qt_plotter(
                capture=capture,
                processor=processor,
                state=state,
                model_path=model_path,
                dataset_path=dataset_path,
                plot_mode=str(args.plot_mode),
                emg_source=str(args.emg_source),
                arduino_alpha=float(args.arduino_alpha),
                feature_window_s=float(args.window_s),
                feature_step_s=max(0.15, float(args.step_s)),
                window_seconds=10.0,
                servo=servo,
            )
        finally:
            try:
                if server is not None:
                    server.shutdown()
            except Exception:
                pass
            try:
                capture.close()
            except Exception:
                pass
            try:
                if servo is not None:
                    servo.close()
            except Exception:
                pass
        return

    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_emg_loop,
        args=(
            capture,
            processor,
            state,
            model_path,
            DEFAULT_LABEL_TO_COMMAND,
            servo,
            float(args.window_s),
            float(args.step_s),
            str(args.plot_mode),
            str(args.emg_source),
            float(args.arduino_alpha),
            stop_event,
            dataset_path,
        ),
        daemon=True,
    )
    try:
        capture.open()
    except Exception as e:
        raise SystemExit(
            f"Falha ao abrir a serial do EMG: {e}\n"
            "Dica: feche o Serial Monitor/Serial Plotter da IDE do Arduino (eles travam a porta)."
        )
    print(f"EMG conectado em {capture.port} @ {args.emg_baud} baud", flush=True)
    thread.start()

    y_max = float(args.y_max)
    y_ticks_raw = str(args.y_ticks)
    if str(args.plot_mode) in ("arduino", "auto") and y_max <= 500.0 and y_ticks_raw.strip() == "0,100,200,300,400":
        y_max = 1023.0
        y_ticks_raw = "0,200,400,600,800,1000"

    try:
        y_ticks = [float(x.strip()) for x in y_ticks_raw.split(",") if x.strip()]
    except Exception:
        y_ticks = [0.0, 100.0, 200.0, 300.0, 400.0]

    try:
        if args.no_gui:
            while True:
                time.sleep(1.0)
                s = state.latest()
                if s is None:
                    continue
                peak = None
                mean = None
                if s.features:
                    peak = s.features.get("peak_freq_hz")
                    mean = s.features.get("mean_freq_hz")
                if peak is not None and mean is not None:
                    print(
                        f"amplitude={s.envelope:.2f} raw={s.raw:.0f} freq_pico={float(peak):.1f}Hz freq_media={float(mean):.1f}Hz",
                        flush=True,
                    )
                elif peak is not None:
                    print(
                        f"amplitude={s.envelope:.2f} raw={s.raw:.0f} freq_pico={float(peak):.1f}Hz",
                        flush=True,
                    )
                else:
                    print(f"amplitude={s.envelope:.2f} raw={s.raw:.0f} filtrado={s.filtered:.2f}", flush=True)
        else:
            run_gui(state, window_seconds=10.0, plot_mode=str(args.plot_mode), y_max=y_max, y_ticks=y_ticks)
    finally:
        stop_event.set()
        try:
            if server is not None:
                server.shutdown()
        except Exception:
            pass
        try:
            capture.close()
        except Exception:
            pass
        try:
            if servo is not None:
                servo.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
