#!/usr/bin/env python3
"""tSPA Designer - graphical calculator for heat-sealed textile soft pneumatic actuators.

Implements the process-window and structural-capacity models of
Zournatzis et al., "Towards a Parametrized Fabrication Framework for Fabric
Soft Pneumatic Actuators" (see README.md / CITATION.cff).

Run:   python tspa_designer_gui.py          (requires: pip install pyside6)
Build: see build_windows.bat
"""
import math
import sys

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDoubleSpinBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from tspa_designer import (
    DENIER, K, KS_ELONG, N_CRIT, T_MAX, WINDOW,
    failure_pressure_kPa, n_crit_from_denier, t_min_from_denier,
)

ACCENT = "#2563eb"
BG = "#f4f6fb"
CARD = "#ffffff"
TEXT = "#1f2937"
MUTED = "#6b7280"
WARN = "#b45309"
CUSTOM = "Custom double-sided fabric (enter denier)"

STYLE = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-family: 'Segoe UI', 'Helvetica Neue', Arial; font-size: 10.5pt; }}
QFrame#card {{ background: {CARD}; border-radius: 14px; border: 1px solid #e5e7eb; }}
QLabel#title {{ font-size: 18pt; font-weight: 700; color: {TEXT}; background: transparent; }}
QLabel#subtitle {{ color: {MUTED}; background: transparent; }}
QLabel#section {{ font-size: 9pt; font-weight: 700; color: {MUTED}; letter-spacing: 1px; background: transparent; }}
QLabel#big {{ font-size: 26pt; font-weight: 700; color: {ACCENT}; background: transparent; }}
QLabel#value {{ font-size: 13pt; font-weight: 600; background: transparent; }}
QLabel#small {{ color: {MUTED}; font-size: 9pt; background: transparent; }}
QLabel#warn {{ color: {WARN}; font-size: 9.5pt; background: #fffbeb; border-radius: 8px; padding: 6px; }}
QLabel {{ background: transparent; }}
QComboBox, QDoubleSpinBox {{ background: white; border: 1px solid #d1d5db; border-radius: 8px; padding: 5px 8px; min-height: 24px; }}
QComboBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QPushButton {{ background: white; border: 1px solid #d1d5db; border-radius: 8px; padding: 6px 14px; }}
QPushButton:checked {{ background: {ACCENT}; color: white; border: 1px solid {ACCENT}; }}
QSlider::groove:horizontal {{ height: 6px; background: #e5e7eb; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; border: 2px solid {ACCENT}; width: 16px; margin: -6px 0; border-radius: 9px; }}
"""


def card():
    f = QFrame()
    f.setObjectName("card")
    return f


def label(text, name=None):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    return lab


class ChamberSketch(QWidget):
    """Top view of the chamber with its maximum inscribed circle and seam."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(150)
        self.dinc, self.w, self.elongated = 60.0, 4.0, False

    def update_geom(self, dinc, w, elongated):
        self.dinc, self.w, self.elongated = dinc, w, elongated
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        aspect = 2.6 if self.elongated else 1.0
        inner_w, inner_h = self.dinc * aspect, self.dinc
        total_w, total_h = inner_w + 2 * self.w, inner_h + 2 * self.w
        s = min((W - 30) / total_w, (H - 30) / total_h)
        cx, cy = W / 2, H / 2
        outer = QRectF(cx - total_w * s / 2, cy - total_h * s / 2, total_w * s, total_h * s)
        inner = QRectF(cx - inner_w * s / 2, cy - inner_h * s / 2, inner_w * s, inner_h * s)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1e3a8a"))
        p.drawRoundedRect(outer, 6, 6)
        p.setBrush(QColor("#dbeafe"))
        p.drawRoundedRect(inner, 4, 4)
        r = self.dinc * s / 2
        p.setPen(QPen(QColor("#dc2626"), 2, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setPen(QColor("#dc2626"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(cx - 60, cy - 10, 120, 20), Qt.AlignCenter, f"D_inc = {self.dinc:.0f} mm")
        p.setPen(QColor("#e5e7eb"))
        p.drawText(QRectF(outer.left(), outer.bottom() - 2, outer.width(), 14), Qt.AlignCenter, "")
        p.end()


class PressureChart(QWidget):
    """Predicted failure pressure versus D_inc, with the current design point."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(190)
        self.n = 7.6
        self.w, self.dinc, self.elong, self.sf = 4.0, 60.0, False, 1.0

    def set_state(self, n, w, dinc, elong, sf):
        self.n, self.w, self.dinc, self.elong, self.sf = n, w, dinc, elong, sf
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        L, R, T, B = 48, 14, 12, 30
        X0, X1 = 30, 200
        xs = [X0 + i for i in range(0, X1 - X0 + 1)]
        ys = [failure_pressure_kPa(self.n, self.w, x, self.elong) for x in xs]
        top = max(ys[0], 100)
        step = next((st for st in (25, 50, 75, 100, 150, 200, 250, 300, 400, 500, 750, 1000) if 4 * st >= top), 1000)
        ymax = 4 * step
        X = lambda x: L + (x - X0) / (X1 - X0) * (W - L - R)
        Y = lambda y: T + (1 - min(y, ymax) / ymax) * (H - T - B)
        # validated band
        p.fillRect(QRectF(X(60), T, X(100) - X(60), H - T - B), QColor("#ecfdf5"))
        p.setPen(QColor("#9ca3af"))
        p.setFont(QFont("Segoe UI", 8))
        for k in range(0, int(ymax) + 1, int(ymax / 4)):
            p.setPen(QPen(QColor("#eef0f4"), 1))
            p.drawLine(QPointF(L, Y(k)), QPointF(W - R, Y(k)))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(0, Y(k) - 8, L - 6, 16), Qt.AlignRight | Qt.AlignVCenter, f"{k}")
        for d in (30, 60, 100, 150, 200):
            p.drawText(QRectF(X(d) - 20, H - B + 4, 40, 14), Qt.AlignCenter, f"{d}")
        p.drawText(QRectF(L, H - 14, W - L - R, 14), Qt.AlignCenter, "Maximum inscribed circle D_inc (mm)")
        p.save(); p.translate(10, H / 2); p.rotate(-90)
        p.drawText(QRectF(-60, -8, 120, 16), Qt.AlignCenter, "P_f (kPa)"); p.restore()
        p.setPen(QColor("#059669"))
        p.drawText(QRectF(X(60), T + 2, X(100) - X(60), 14), Qt.AlignCenter, "validated")
        for curve, colour, style in ((ys, ACCENT, Qt.SolidLine), ([y / self.sf for y in ys], "#94a3b8", Qt.DashLine)):
            path = QPainterPath(QPointF(X(xs[0]), Y(curve[0])))
            for x, y in zip(xs[1:], curve[1:]):
                path.lineTo(X(x), Y(y))
            p.setPen(QPen(QColor(colour), 2.4 if style == Qt.SolidLine else 1.6, style))
            p.drawPath(path)
        pf = failure_pressure_kPa(self.n, self.w, self.dinc, self.elong)
        p.setPen(QPen(QColor("white"), 2))
        p.setBrush(QColor("#dc2626"))
        p.drawEllipse(QPointF(X(self.dinc), Y(pf)), 6, 6)
        p.end()


class Designer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("tSPA Designer")
        self.setStyleSheet(STYLE)
        self.resize(980, 640)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 14)
        root.setSpacing(12)
        root.addWidget(label("tSPA Designer", "title"))
        root.addWidget(label("Process window and allowable pressure of heat-sealed textile soft pneumatic actuators", "subtitle"))
        body = QHBoxLayout(); body.setSpacing(14)
        root.addLayout(body, 1)

        # ---------------- inputs ----------------
        inp = card(); body.addWidget(inp, 0)
        g = QGridLayout(inp); g.setContentsMargins(18, 16, 18, 16); g.setVerticalSpacing(8)
        g.addWidget(label("MATERIAL", "section"), 0, 0, 1, 2)
        self.fabric = QComboBox(); self.fabric.addItems(list(N_CRIT) + [CUSTOM]); self.fabric.setCurrentText("Light Blue 420D")
        g.addWidget(self.fabric, 1, 0, 1, 2)
        g.addWidget(label("Linear mass density (D)"), 2, 0)
        self.denier = QDoubleSpinBox(); self.denier.setRange(70, 1200); self.denier.setDecimals(0); self.denier.setValue(420); self.denier.setSuffix(" D")
        g.addWidget(self.denier, 2, 1)
        g.addWidget(label("GEOMETRY", "section"), 3, 0, 1, 2)
        g.addWidget(label("Seam width w"), 4, 0)
        self.w = QDoubleSpinBox(); self.w.setRange(1, 10); self.w.setSingleStep(0.5); self.w.setValue(4); self.w.setSuffix(" mm")
        g.addWidget(self.w, 4, 1)
        g.addWidget(label("Max. inscribed circle D_inc"), 5, 0)
        self.dinc = QDoubleSpinBox(); self.dinc.setRange(30, 200); self.dinc.setValue(60); self.dinc.setSuffix(" mm")
        g.addWidget(self.dinc, 5, 1)
        self.slider = QSlider(Qt.Horizontal); self.slider.setRange(30, 200); self.slider.setValue(60)
        g.addWidget(self.slider, 6, 0, 1, 2)
        g.addWidget(label("Chamber shape"), 7, 0)
        shp = QHBoxLayout(); self.sq = QPushButton("Square"); self.el = QPushButton("Elongated")
        self.grp = QButtonGroup(self)
        for b in (self.sq, self.el):
            b.setCheckable(True); self.grp.addButton(b); shp.addWidget(b)
        self.sq.setChecked(True)
        g.addLayout(shp, 7, 1)
        g.addWidget(label("SAFETY", "section"), 8, 0, 1, 2)
        g.addWidget(label("Safety factor"), 9, 0)
        self.sf = QDoubleSpinBox(); self.sf.setRange(1, 5); self.sf.setSingleStep(0.25); self.sf.setValue(2)
        g.addWidget(self.sf, 9, 1)
        self.sketch = ChamberSketch(); g.addWidget(self.sketch, 10, 0, 1, 2)
        g.setRowStretch(11, 1)

        # ---------------- results ----------------
        res = QVBoxLayout(); res.setSpacing(12); body.addLayout(res, 1)
        top = QHBoxLayout(); top.setSpacing(12); res.addLayout(top)
        c1 = card(); top.addWidget(c1, 1); v1 = QVBoxLayout(c1); v1.setContentsMargins(18, 14, 18, 14)
        v1.addWidget(label("ALLOWABLE PRESSURE", "section"))
        self.allow = label("-", "big"); v1.addWidget(self.allow)
        self.allow_alt = label("-", "small"); v1.addWidget(self.allow_alt)
        self.pf = label("-", "small"); v1.addWidget(self.pf)
        c2 = card(); top.addWidget(c2, 1); v2 = QVBoxLayout(c2); v2.setContentsMargins(18, 14, 18, 14)
        v2.addWidget(label("SEALING WINDOW (press, 110 s)", "section"))
        self.temp = label("-", "value"); v2.addWidget(self.temp)
        self.pres = label("-", "value"); v2.addWidget(self.pres)
        self.ncrit = label("-", "small"); self.ncrit.setWordWrap(True); v2.addWidget(self.ncrit)
        c3 = card(); res.addWidget(c3, 1); v3 = QVBoxLayout(c3); v3.setContentsMargins(14, 10, 14, 10)
        v3.addWidget(label("FAILURE PRESSURE VS. CHAMBER SIZE   (solid: predicted, dashed: allowable)", "section"))
        self.chart = PressureChart(); v3.addWidget(self.chart, 1)
        self.warn = label("", "warn"); self.warn.setWordWrap(True); res.addWidget(self.warn)
        root.addWidget(label("Zournatzis et al., Towards a Parametrized Fabrication Framework for Fabric Soft Pneumatic Actuators. "
                             "Validated range: 70-840D, w = 2-8 mm, D_inc = 60-100 mm. Estimates only; verify designs experimentally.", "small"))

        # ---------------- signals ----------------
        self.fabric.currentTextChanged.connect(self.on_fabric)
        for wdg in (self.denier, self.w, self.dinc, self.sf):
            wdg.valueChanged.connect(self.recalc)
        self.slider.valueChanged.connect(lambda v: self.dinc.setValue(v))
        self.dinc.valueChanged.connect(lambda v: self.slider.setValue(int(round(v))))
        self.grp.buttonClicked.connect(lambda _: self.recalc())
        self.on_fabric(self.fabric.currentText())

    def on_fabric(self, name):
        custom = name == CUSTOM
        self.denier.setEnabled(custom)
        if not custom:
            self.denier.blockSignals(True); self.denier.setValue(DENIER[name]); self.denier.blockSignals(False)
        self.recalc()

    def recalc(self):
        name = self.fabric.currentText(); d = self.denier.value()
        w, dinc, sf, elong = self.w.value(), self.dinc.value(), self.sf.value(), self.el.isChecked()
        warns = []
        if name == CUSTOM:
            n = n_crit_from_denier(d); tmin = t_min_from_denier(d); pmin = "0.6" if d <= 300 else "0.5"
            self.temp.setText(f"Temperature  {min(tmin, T_MAX):.0f} - {T_MAX:.0f} °C")
            self.pres.setText(f"Pressure  ≥ {pmin} MPa")
            src = "interpolation law"
            if not 210 <= d <= 840:
                warns.append("Denier outside 210-840 D: interpolation laws not validated.")
            if tmin >= T_MAX:
                warns.append("Estimated sealing window is empty (T_min ≥ 175 °C).")
        else:
            n = N_CRIT[name]; src = "measured"
            if name in WINDOW:
                tmin, pmin = WINDOW[name]
                self.temp.setText(f"Temperature  {tmin} - {T_MAX:.0f} °C")
                self.pres.setText("Pressure  ≥ 0.5 MPa (any tested)" if pmin.startswith("any") else f"Pressure  {pmin} MPa")
            else:
                self.temp.setText("Single-sided fabric")
                self.pres.setText("Substrate-limited; no window defined")
            if "840D" in name:
                warns.append("N_crit of 840D is a lower bound (specimens failed at the fitting).")
        if not 2 <= w <= 8: warns.append("Seam width outside the tested 2-8 mm range.")
        if w < 3: warns.append("w < 3 mm: below the critical seam width (≈ 2.9 mm).")
        if not 60 <= dinc <= 100: warns.append("D_inc outside the validated 60-100 mm range (extrapolation).")
        pf = failure_pressure_kPa(n, w, dinc, elong)
        allow = pf / sf
        self.allow.setText(f"{allow:.0f} kPa")
        self.allow_alt.setText(f"{allow / 100:.2f} bar  ·  {allow / 6.894757:.1f} psi")
        self.pf.setText(f"Predicted failure pressure: {pf:.0f} kPa (SF {sf:g})")
        self.ncrit.setText(f"Seam capacity N_crit = {n:.2f} N/mm ({src})\nShape factor k_s = {KS_ELONG if elong else 1:.2f}")
        self.chart.set_state(n, w, dinc, elong, sf)
        self.sketch.update_geom(dinc, w, elong)
        self.warn.setVisible(bool(warns))
        self.warn.setText("⚠  " + "\n⚠  ".join(warns))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Designer()
    win.show()
    sys.exit(app.exec())
