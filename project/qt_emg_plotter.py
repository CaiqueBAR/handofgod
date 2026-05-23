from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Optional

import numpy as np

try:
    from .emg_interface import run_emg_loop
    from .servo_controller import DEFAULT_LABEL_TO_COMMAND, ServoSerialController
except Exception:
    from project.emg_interface import run_emg_loop
    from project.servo_controller import DEFAULT_LABEL_TO_COMMAND, ServoSerialController


def run_qt_plotter(
    *,
    capture,
    processor,
    state,
    model_path,
    dataset_path,
    plot_mode: str,
    emg_source: str,
    arduino_alpha: float,
    feature_window_s: float,
    feature_step_s: float,
    window_seconds: float,
    servo: Optional[ServoSerialController] = None,
) -> None:
    from PySide6 import QtCore, QtGui, QtWidgets

    import pyqtgraph as pg
    try:
        pg.setConfigOption("useOpenGL", True)
    except Exception:
        pass

    class EmgController(QtCore.QObject):
        def __init__(self) -> None:
            super().__init__()
            self._thread: Optional[threading.Thread] = None
            self._stop_event = threading.Event()
            self._running = False

        @property
        def running(self) -> bool:
            return self._running

        def start(self) -> tuple[bool, str]:
            if self._running:
                return True, "already_running"

            try:
                capture.open()
            except Exception as e:
                return False, str(e)

            self._stop_event = threading.Event()
            self._thread = threading.Thread(
                target=run_emg_loop,
                args=(
                    capture,
                    processor,
                    state,
                    model_path,
                    DEFAULT_LABEL_TO_COMMAND,
                    servo,
                    float(feature_window_s),
                    float(feature_step_s),
                    str(plot_mode),
                    str(emg_source),
                    float(arduino_alpha),
                    self._stop_event,
                    dataset_path,
                ),
                daemon=True,
            )
            self._thread.start()
            self._running = True
            return True, "running"

        def stop(self) -> None:
            if not self._running:
                return
            self._stop_event.set()
            th = self._thread
            if th is not None:
                th.join(timeout=2.0)
            try:
                capture.close()
            except Exception:
                pass
            self._running = False

    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("emg_interface")
            self.resize(1200, 700)

            self._controller = EmgController()
            self._q = state.add_status_listener()
            self._t0: Optional[float] = None

            self._max_points = int(max(800.0, float(window_seconds) * 600.0))
            self._x: Deque[float] = deque(maxlen=self._max_points)
            self._raw: Deque[float] = deque(maxlen=self._max_points)
            self._filt: Deque[float] = deque(maxlen=self._max_points)
            self._env: Deque[float] = deque(maxlen=self._max_points)
            self._peak: Deque[float] = deque(maxlen=self._max_points)
            self._mean: Deque[float] = deque(maxlen=self._max_points)

            self._last_peak: Optional[float] = None
            self._last_mean: Optional[float] = None

            root = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(root)
            layout.setContentsMargins(14, 10, 14, 10)
            layout.setSpacing(10)

            top = QtWidgets.QWidget()
            top_l = QtWidgets.QHBoxLayout(top)
            top_l.setContentsMargins(0, 0, 0, 0)
            top_l.setSpacing(10)

            self._conn_label = QtWidgets.QLabel(self._format_conn_label(False))
            self._conn_label.setObjectName("connLabel")
            top_l.addWidget(self._conn_label, 1)

            self._state_label = QtWidgets.QLabel("-")
            self._state_label.setObjectName("stateLabel")
            top_l.addWidget(self._state_label, 0)

            self._interp_label = QtWidgets.QLabel("Interpolate")
            self._interp_toggle = QtWidgets.QCheckBox()
            self._interp_toggle.setChecked(True)
            top_l.addWidget(self._interp_label, 0)
            top_l.addWidget(self._interp_toggle, 0)

            self._run_btn = QtWidgets.QPushButton("RUN")
            self._run_btn.setObjectName("runButton")
            self._run_btn.clicked.connect(self._toggle_run)
            top_l.addWidget(self._run_btn, 0)

            self._menu_btn = QtWidgets.QToolButton()
            self._menu_btn.setText("≡")
            self._menu_btn.setObjectName("menuButton")
            self._menu_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
            self._menu_btn.setMenu(self._build_menu())
            top_l.addWidget(self._menu_btn, 0)

            layout.addWidget(top)

            pg.setConfigOptions(antialias=True)
            self._plot = pg.PlotWidget()
            self._plot.setBackground("#0e141a")
            self._plot.showGrid(x=True, y=True, alpha=0.25)
            self._plot.getAxis("left").setPen(pg.mkPen("#a9b4c2"))
            self._plot.getAxis("bottom").setPen(pg.mkPen("#a9b4c2"))
            self._plot.getAxis("left").setTextPen(pg.mkPen("#a9b4c2"))
            self._plot.getAxis("bottom").setTextPen(pg.mkPen("#a9b4c2"))
            self._plot.setMouseEnabled(x=False, y=False)

            self._raw_curve = self._plot.plot([], [], pen=pg.mkPen("#2dd4bf", width=2))
            self._filt_curve = self._plot.plot([], [], pen=pg.mkPen("#fb923c", width=2))
            self._env_curve = self._plot.plot([], [], pen=pg.mkPen("#22c55e", width=2))
            self._peak_curve = self._plot.plot([], [], pen=pg.mkPen("#a78bfa", width=2))
            self._mean_curve = self._plot.plot([], [], pen=pg.mkPen("#facc15", width=2))

            for c in (self._raw_curve, self._filt_curve, self._env_curve, self._peak_curve, self._mean_curve):
                try:
                    c.setDownsampling(auto=True, method="peak")
                except Exception:
                    pass
                try:
                    c.setClipToView(True)
                except Exception:
                    pass

            layout.addWidget(self._plot, 1)

            bottom = QtWidgets.QWidget()
            bottom_l = QtWidgets.QHBoxLayout(bottom)
            bottom_l.setContentsMargins(0, 0, 0, 0)
            bottom_l.setSpacing(10)

            self._tx = QtWidgets.QLineEdit()
            self._tx.setPlaceholderText("Type Message")
            self._tx.returnPressed.connect(self._send_message)
            bottom_l.addWidget(self._tx, 1)

            self._send_btn = QtWidgets.QPushButton("SEND")
            self._send_btn.setObjectName("sendButton")
            self._send_btn.clicked.connect(self._send_message)
            bottom_l.addWidget(self._send_btn, 0)

            self._newline = QtWidgets.QComboBox()
            self._newline.addItems(["New Line", "LF", "CRLF", "None"])
            bottom_l.addWidget(self._newline, 0)

            bottom_l.addStretch(1)

            self._select = QtWidgets.QComboBox()
            self._select.setEditable(False)
            self._select.addItems(
                [
                    "Select...",
                    "Raw + Filtered",
                    "Envelope",
                    "Peak Frequency (Hz)",
                    "Mean Frequency (Hz)",
                ]
            )
            self._select.setCurrentIndex(1)
            bottom_l.addWidget(self._select, 0)

            layout.addWidget(bottom)

            self.setCentralWidget(root)
            self.statusBar().showMessage("Board disconnected")

            self._timer = QtCore.QTimer(self)
            self._timer.setInterval(33)
            self._timer.timeout.connect(self._refresh)
            self._timer.start()

            self._apply_theme()
            self._apply_visibility()
            self._apply_interpolate_style()
            self._interp_toggle.toggled.connect(self._apply_interpolate_style)
            self._select.currentIndexChanged.connect(self._apply_visibility)

        def closeEvent(self, event: QtGui.QCloseEvent) -> None:
            try:
                self._controller.stop()
                try:
                    state.remove_status_listener(self._q)
                except Exception:
                    pass
            finally:
                event.accept()

        def _build_menu(self) -> QtWidgets.QMenu:
            menu = QtWidgets.QMenu(self)

            act_refresh = QtGui.QAction("Refresh ports", self)
            act_refresh.triggered.connect(self._refresh_ports_menu)
            menu.addAction(act_refresh)

            act_cal = QtGui.QAction("Calibrate (2s)", self)
            act_cal.triggered.connect(lambda: self._calibrate(2.0))
            menu.addAction(act_cal)

            act_cal5 = QtGui.QAction("Calibrate (5s)", self)
            act_cal5.triggered.connect(lambda: self._calibrate(5.0))
            menu.addAction(act_cal5)

            self._ports_menu = menu.addMenu("Port")
            self._baud_menu = menu.addMenu("Baud")

            for b in [9600, 19200, 38400, 57600, 115200, 230400]:
                a = QtGui.QAction(str(b), self)
                a.setCheckable(True)
                a.setChecked(int(getattr(capture, "_baud", 115200)) == int(b))
                a.triggered.connect(lambda _=False, bb=b: self._set_baud(int(bb)))
                self._baud_menu.addAction(a)

            self._refresh_ports_menu()
            return menu

        def _calibrate(self, seconds: float) -> None:
            state.request_calibration(float(seconds))
            self.statusBar().showMessage(f"Calibrating... ({float(seconds):.0f}s)")

        def _refresh_ports_menu(self) -> None:
            self._refresh_ports_menu_impl()

        def _refresh_ports_menu_impl(self) -> None:
            try:
                try:
                    from .utils import list_serial_ports
                except Exception:
                    from project.utils import list_serial_ports
                ports = list_serial_ports()
            except Exception:
                ports = []

            self._ports_menu.clear()
            for p in ports:
                a = QtGui.QAction(f"{p.device}  {p.description}", self)
                a.setCheckable(True)
                a.setChecked(str(getattr(capture, "_port", "auto")) == str(p.device))
                a.triggered.connect(lambda _=False, dev=p.device: self._set_port(str(dev)))
                self._ports_menu.addAction(a)

            a_auto = QtGui.QAction("auto", self)
            a_auto.setCheckable(True)
            a_auto.setChecked(str(getattr(capture, "_port", "auto")) == "auto")
            a_auto.triggered.connect(lambda _=False: self._set_port("auto"))
            self._ports_menu.addAction(a_auto)

        def _set_port(self, port: str) -> None:
            if self._controller.running:
                self._controller.stop()
            setattr(capture, "_port", port)
            self._conn_label.setText(self._format_conn_label(False))
            self.statusBar().showMessage("Board disconnected")

        def _set_baud(self, baud: int) -> None:
            if self._controller.running:
                self._controller.stop()
            setattr(capture, "_baud", int(baud))
            self._conn_label.setText(self._format_conn_label(False))
            self.statusBar().showMessage("Board disconnected")

        def _format_conn_label(self, connected: bool) -> str:
            if connected:
                p = str(getattr(capture, "port", getattr(capture, "_port", "auto")))
                b = str(getattr(capture, "_baud", 115200))
            else:
                p = str(getattr(capture, "_port", "auto"))
                b = str(getattr(capture, "_baud", 115200))
            status = "connected" if connected else "disconnected"
            return f"/serial/{p}/{b} ({status})"

        def _toggle_run(self) -> None:
            if self._controller.running:
                self._controller.stop()
                self._run_btn.setText("RUN")
                self._conn_label.setText(self._format_conn_label(False))
                self.statusBar().showMessage("Board disconnected")
                try:
                    self._q.clear()
                except Exception:
                    pass
                return

            ok, msg = self._controller.start()
            if not ok:
                self.statusBar().showMessage("Board disconnected")
                self._conn_label.setText(self._format_conn_label(False))
                box = QtWidgets.QMessageBox(self)
                box.setIcon(QtWidgets.QMessageBox.Critical)
                box.setWindowTitle("Serial")
                box.setText("Falha ao abrir a porta serial.")
                box.setInformativeText(
                    "Feche Arduino IDE (Serial Monitor/Plotter) e qualquer app que esteja usando a porta, e tente de novo."
                )
                box.setDetailedText(str(msg))
                box.exec()
                return

            self._run_btn.setText("STOP")
            self._conn_label.setText(self._format_conn_label(True))
            self.statusBar().showMessage("Running")

            self._t0 = None
            try:
                self._q.clear()
            except Exception:
                pass
            self._x.clear()
            self._raw.clear()
            self._filt.clear()
            self._env.clear()
            self._peak.clear()
            self._mean.clear()
            self._last_peak = None
            self._last_mean = None

        def _send_message(self) -> None:
            text = self._tx.text().strip()
            if not text:
                return
            if not self._controller.running:
                self.statusBar().showMessage("Board disconnected")
                return

            nl_idx = int(self._newline.currentIndex())
            newline = "\n"
            if nl_idx == 1:
                newline = "\n"
            elif nl_idx == 2:
                newline = "\r\n"
            elif nl_idx == 3:
                newline = ""

            try:
                if newline == "":
                    capture.write_text(text, newline="")
                else:
                    capture.write_text(text, newline=newline)
                self._tx.clear()
            except Exception as e:
                self.statusBar().showMessage(f"Send failed: {e}")

        def _apply_visibility(self) -> None:
            mode = str(self._select.currentText())
            if mode.startswith("Select"):
                mode = "Raw + Filtered"

            show_raw = mode == "Raw + Filtered"
            show_filt = mode == "Raw + Filtered"
            show_env = mode == "Envelope"
            show_peak = mode == "Peak Frequency (Hz)"
            show_mean = mode == "Mean Frequency (Hz)"

            self._raw_curve.setVisible(show_raw)
            self._filt_curve.setVisible(show_filt)
            self._env_curve.setVisible(show_env)
            self._peak_curve.setVisible(show_peak)
            self._mean_curve.setVisible(show_mean)

        def _apply_interpolate_style(self) -> None:
            on = bool(self._interp_toggle.isChecked())

            def _apply(curve, color: str) -> None:
                if on:
                    curve.setPen(pg.mkPen(color, width=2))
                    curve.setSymbol(None)
                else:
                    curve.setPen(None)
                    curve.setSymbol("o")
                    curve.setSymbolSize(4)
                    curve.setSymbolBrush(pg.mkBrush(color))
                    curve.setSymbolPen(pg.mkPen(color))

            _apply(self._raw_curve, "#2dd4bf")
            _apply(self._filt_curve, "#fb923c")
            _apply(self._env_curve, "#22c55e")
            _apply(self._peak_curve, "#a78bfa")
            _apply(self._mean_curve, "#facc15")

        def _drain_state(self) -> bool:
            new = []
            try:
                while self._q:
                    new.append(self._q.popleft())
                    if len(new) >= 5000:
                        break
            except Exception:
                return False

            if not new:
                return False

            if self._t0 is None:
                self._t0 = float(new[0].t)

            for s in new:
                x = float(s.t) - float(self._t0)
                self._x.append(x)
                self._raw.append(float(s.raw))
                self._filt.append(float(s.filtered))
                self._env.append(float(s.envelope))
                if getattr(s, "interpretation", None):
                    try:
                        st = str((s.interpretation or {}).get("state") or "-")
                        act = (s.interpretation or {}).get("activation")
                        note = (s.interpretation or {}).get("note")
                        if act is not None:
                            txt = f"{st}  x{float(act):.1f}"
                        else:
                            txt = st
                        if note:
                            txt = f"{txt}  ({note})"
                        self._state_label.setText(txt)
                    except Exception:
                        pass
                if s.features:
                    if "peak_freq_hz" in s.features:
                        try:
                            self._last_peak = float(s.features.get("peak_freq_hz"))
                        except Exception:
                            pass
                    if "mean_freq_hz" in s.features:
                        try:
                            self._last_mean = float(s.features.get("mean_freq_hz"))
                        except Exception:
                            pass
                self._peak.append(float(self._last_peak) if self._last_peak is not None else float("nan"))
                self._mean.append(float(self._last_mean) if self._last_mean is not None else float("nan"))

            return True

        def _refresh(self) -> None:
            if not self._drain_state():
                return

            x = np.fromiter(self._x, dtype=np.float64, count=len(self._x))
            if self._raw_curve.isVisible():
                y = np.fromiter(self._raw, dtype=np.float64, count=len(self._raw))
                self._raw_curve.setData(x, y, skipFiniteCheck=True)
            if self._filt_curve.isVisible():
                y = np.fromiter(self._filt, dtype=np.float64, count=len(self._filt))
                self._filt_curve.setData(x, y, skipFiniteCheck=True)
            if self._env_curve.isVisible():
                y = np.fromiter(self._env, dtype=np.float64, count=len(self._env))
                self._env_curve.setData(x, y, skipFiniteCheck=True)
            if self._peak_curve.isVisible():
                y = np.fromiter(self._peak, dtype=np.float64, count=len(self._peak))
                self._peak_curve.setData(x, y, skipFiniteCheck=True)
            if self._mean_curve.isVisible():
                y = np.fromiter(self._mean, dtype=np.float64, count=len(self._mean))
                self._mean_curve.setData(x, y, skipFiniteCheck=True)

            x_max = float(x[-1]) if len(x) else 0.0
            self._plot.setXRange(max(0.0, x_max - float(window_seconds)), x_max, padding=0.0)

        def _apply_theme(self) -> None:
            self.setStyleSheet(
                """
                QMainWindow { background: #0b1116; }
                QLabel#connLabel { color: #c7d2de; font-size: 12px; }
                QLabel#stateLabel {
                    color: #c7d2de;
                    font-size: 12px;
                    border: 1px solid #1f2a33;
                    border-radius: 10px;
                    padding: 6px 10px;
                    background: #0e141a;
                }
                QLabel { color: #c7d2de; }
                QLineEdit {
                    background: #0e141a;
                    color: #c7d2de;
                    border: 1px solid #1f2a33;
                    border-radius: 10px;
                    padding: 10px 12px;
                }
                QComboBox {
                    background: #0e141a;
                    color: #c7d2de;
                    border: 1px solid #1f2a33;
                    border-radius: 10px;
                    padding: 8px 10px;
                }
                QPushButton#sendButton {
                    background: #14b8a6;
                    color: #05202a;
                    border: none;
                    border-radius: 10px;
                    padding: 10px 18px;
                    font-weight: 600;
                }
                QPushButton#sendButton:pressed { background: #0f9f90; }
                QPushButton#runButton {
                    background: #7f1d1d;
                    color: #f8fafc;
                    border: none;
                    border-radius: 12px;
                    padding: 10px 18px;
                    font-weight: 700;
                }
                QPushButton#runButton:pressed { background: #6b1010; }
                QToolButton#menuButton {
                    background: transparent;
                    color: #c7d2de;
                    border: none;
                    font-size: 18px;
                    padding: 6px 10px;
                }
                QCheckBox { spacing: 8px; }
                QCheckBox::indicator {
                    width: 46px;
                    height: 24px;
                    border-radius: 12px;
                    background: #1f2a33;
                }
                QCheckBox::indicator:checked { background: #14b8a6; }
                QCheckBox::indicator::unchecked { background: #1f2a33; }
                QStatusBar { color: #c7d2de; background: transparent; }
                """
            )

    app = QtWidgets.QApplication([])
    app.setApplicationName("emg_interface")
    w = MainWindow()
    w.show()
    app.exec()
