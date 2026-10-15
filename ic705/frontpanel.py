# SPDX-License-Identifier: GPL-3.0-or-later
"""Painted IC-705-inspired faceplate. Meter values are decorative, never RSSI."""
import math
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QSize
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QRadialGradient,
                           QPainter, QPen, QPainterPath)
from PySide6.QtWidgets import QWidget


class FrontPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(310)
        self.setMinimumWidth(800)
        self.setSizePolicy(self.sizePolicy().Policy.Expanding, self.sizePolicy().Policy.Expanding)
        self.mode = 'IDLE'
        self.station = ''
        self.reflector = 'REF030C'
        self.local_call = ''
        self.radio_ok = False
        self.linked = False
        self.link_text = 'DISCONNECTED'
        self.level = 0.0
        self.peak = 0.0
        self.phase = 0
        self.animate = True
        self.preview_mode = False
        self.setToolTip('RX / TX follows actual DV stream activity. The animated S-meter and trace are simulated. Knobs are decorative; use your radio microphone and PTT.')
        self.setAccessibleName('IC-705-inspired status display; simulated signal meter')
        self.timer = QTimer(self, interval=80)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def sizeHint(self):
        return QSize(1000, 410)

    def set_activity(self, text):
        self.mode = 'TX' if text.startswith('TX') else 'RX' if text.startswith('RX') else 'IDLE'
        self.station = text.split('•', 1)[1].strip() if '•' in text else ''
        if self.mode == 'IDLE':
            self.level = self.peak = 0.0
        self.setAccessibleDescription(f'{self.mode}. {self.station}. Signal meter simulated, not RF strength.')
        self.update()

    def set_radio(self, ok):
        self.radio_ok = ok
        self.update()

    def set_network(self, text):
        self.linked = 'accepted link' in text
        self.link_text = 'LINKED / D-PLUS' if self.linked else 'DISCONNECTED' if text == 'Disconnected' else 'CONNECTING' if ('Waiting' in text or text.startswith('Linking')) else 'CHECK CONNECTION'
        self.update()

    def tick(self):
        if self.mode != 'IDLE' and self.animate:
            self.phase += 1
            target = 13 + 5 * math.sin(self.phase * .43) + 3 * math.sin(self.phase * 1.17)
            self.level += (max(2, min(24, target)) - self.level) * .55
            self.peak = max(self.level, self.peak - .3)
            self.update()
        elif self.level or self.peak:
            self.level = self.peak = 0
            self.update()

    def set_animation(self, enabled):
        self.animate = enabled
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scale = min(self.width() / 1000, self.height() / 410)
        p.translate((self.width() - 1000 * scale) / 2, (self.height() - 410 * scale) / 2)
        p.scale(scale, scale)

        def rect(x, y, w, h, color, radius=0, border=None):
            p.setPen(QPen(QColor(border), 1) if border else Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(x, y, w, h), radius, radius)

        def text(x, y, w, h, value, size=12, color='#d3d9df', bold=False,
                 align=Qt.AlignLeft | Qt.AlignVCenter, family='Segoe UI'):
            p.setPen(QColor(color))
            p.setFont(QFont(family, size, QFont.Bold if bold else QFont.Normal))
            p.drawText(QRectF(x, y, w, h), align, value)

        def lamp(x, y, on, color):
            if on:
                glow = QRadialGradient(QPointF(x, y), 12)
                glow.setColorAt(0, QColor(color))
                glow.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(glow); p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x, y), 12, 12)
            p.setBrush(QColor(color if on else '#303639'))
            p.setPen(QPen(QColor('#07090b'), 1))
            p.drawEllipse(QPointF(x, y), 4, 4)

        # Chunky black faceplate and moulded side grips.
        chassis = QLinearGradient(0, 0, 0, 410)
        for stop, color in [(0, '#42474c'), (.08, '#24282c'), (.6, '#181c20'), (1, '#0c0f12')]:
            chassis.setColorAt(stop, QColor(color))
        p.setBrush(chassis); p.setPen(QPen(QColor('#4b5055'), 2))
        p.drawRoundedRect(QRectF(7, 9, 986, 390), 22, 22)
        for x in (11, 963):
            rect(x, 37, 25, 318, '#111418', 7, '#33383e')
            for y in range(62, 340, 19):
                rect(x+4, y, 17, 4, '#252a2e', 1)
        for x, y in [(45, 34), (952, 34), (45, 373), (952, 373)]:
            p.setBrush(QColor('#0c0e11')); p.setPen(QPen(QColor('#4c5156'), 1))
            p.drawEllipse(QPointF(x, y), 5, 5)
            p.drawLine(QPointF(x-2, y-2), QPointF(x+2, y+2))
        text(125, 17, 255, 34, 'IC-705', 23, '#f0f1f2', True)
        text(272, 22, 400, 28, 'D-STAR  /  USB TERMINAL', 10, '#b3bac0')
        text(789, 20, 145, 26, 'HamTec', 17, '#f2f3f4', True, Qt.AlignRight | Qt.AlignVCenter)

        # Display bezel / glass.
        rect(115, 54, 646, 292, '#07090c', 7, '#484e53')
        rect(125, 64, 626, 272, '#061321', 2, '#23435c')
        rect(126, 65, 624, 27, '#14334b')
        text(139, 65, 185, 27, 'DV    D-STAR', 11, '#edfaff', True)
        text(344, 65, 180, 27, 'TERMINAL  /  USB', 10, '#b7deef')
        text(568, 65, 167, 27, 'MODULE  C', 11, '#68ddff', True, Qt.AlignRight | Qt.AlignVCenter)
        # Activity LEDs from actual gateway state.
        for x, label, active, color in [(148, 'RX', self.mode == 'RX', '#65ee60'),
                (216, 'TX', self.mode == 'TX', '#ff5353'),
                (294, 'USB', self.radio_ok, '#58d5ff'),
                (380, 'LINK', self.linked, '#59e8bd')]:
            lamp(x, 109, active, color)
            text(x+11, 97, 58, 24, label, 9, color if active else '#566b80', True)
        text(518, 97, 215, 24, 'UI PREVIEW' if self.preview_mode else 'USB DIGITAL VOICE', 9, '#93a7b9', False, Qt.AlignRight | Qt.AlignVCenter)
        text(140, 122, 480, 58, self.reflector, 39, '#84e4ff', True, family='Consolas')
        rect(641, 133, 89, 30, '#153641', 3, '#336b77')
        text(641, 133, 89, 30, 'D-PLUS', 11, '#95eee0', True, Qt.AlignCenter)
        text(143, 181, 260, 24, 'MY  ' + (self.local_call or 'SET CALLSIGN'), 11, '#e8f2ff', True, family='Consolas')
        mode_color = '#ff6c6c' if self.mode == 'TX' else '#8cf77c' if self.mode == 'RX' else '#a5b6c6'
        text(430, 181, 300, 24, (self.mode+'  '+self.station) if self.mode != 'IDLE' else 'STANDBY', 12, mode_color, True, Qt.AlignRight | Qt.AlignVCenter, 'Consolas')
        p.setPen(QPen(QColor('#28455e'), 1)); p.drawLine(142, 211, 733, 211)
        text(143, 214, 260, 20, 'SIMULATED S-METER', 8, '#8da5ba', True)
        text(451, 214, 281, 20, 'ANIMATION OFF' if not self.animate else 'NO RF MEASUREMENT', 8, '#8da5ba', False, Qt.AlignRight | Qt.AlignVCenter)
        for i in range(27):
            color = '#55dcec' if i < 15 else '#f5c966' if i < 22 else '#fc6d60'
            rect(145+i*21.7, 243, 17, 13, color if i < self.level else '#163047', 1)
        if self.peak > 0:
            rect(145+min(26, int(self.peak))*21.7, 239, 17, 2, '#f7faff')
        for i, value in [(0, 'S1'), (4, '3'), (8, '5'), (12, '7'), (16, '9'), (20, '+20'), (24, '+40')]:
            text(145+i*21.7, 257, 48, 15, value, 8, '#95aec4')
        # Decorative DV trace; only animates while actual stream activity is present.
        rect(143, 280, 590, 27, '#071c30')
        for y in (287, 299):
            p.setPen(QPen(QColor('#18334d'), .6)); p.drawLine(145, y, 730, y)
        path = QPainterPath(QPointF(145, 294))
        for x in range(0, 586, 3):
            amplitude = 0
            if self.mode != 'IDLE' and self.animate:
                amplitude = (math.sin(x*.19+self.phase*.67) * math.sin(x*.043-self.phase*.18) * 9)
            path.lineTo(145+x, 294+amplitude)
        p.setPen(QPen(QColor('#ee967c' if self.mode == 'TX' else '#53b8ff'), 1.2)); p.drawPath(path)
        text(144, 309, 360, 21, self.link_text, 8, '#6de8bf' if self.linked else '#a4b4c7', True)
        text(502, 309, 229, 21, 'DECORATIVE DV TRACE', 8, '#829db4', False, Qt.AlignRight | Qt.AlignVCenter)

        def knob(cx, cy, r, title):
            grad = QRadialGradient(QPointF(cx-r*.3, cy-r*.45), r*1.7)
            grad.setColorAt(0, QColor('#666b70')); grad.setColorAt(.5, QColor('#2c3136')); grad.setColorAt(1, QColor('#101318'))
            p.setBrush(grad); p.setPen(QPen(QColor('#090b0d'), 3))
            p.drawEllipse(QPointF(cx, cy), r, r)
            for i in range(64):
                a = i*math.pi/32
                p.setPen(QPen(QColor('#5a6066' if i % 2 else '#0b0e11'), 1))
                p.drawLine(QPointF(cx+math.cos(a)*(r-6), cy+math.sin(a)*(r-6)), QPointF(cx+math.cos(a)*(r-1), cy+math.sin(a)*(r-1)))
            p.setBrush(QColor('#252a2f')); p.setPen(QPen(QColor('#70757b'), 1))
            p.drawEllipse(QPointF(cx, cy), r*.72, r*.72)
            p.setBrush(QColor('#1a1e23')); p.setPen(QPen(QColor('#42484e'), 1))
            p.drawEllipse(QPointF(cx+r*.28, cy+r*.28), r*.19, r*.19)
            text(cx-r-12, cy+r+8, r*2+24, 21, title, 8, '#b3bac0', True, Qt.AlignCenter)
        knob(76, 153, 28, 'AF / RF / SQL')
        knob(76, 270, 25, 'MULTI')
        text(41, 78, 70, 25, 'POWER', 8, '#d2d8df', True, Qt.AlignCenter)
        lamp(76, 72, self.radio_ok, '#61e690')
        for y in range(68, 135, 8):
            rect(800, y, 127, 3, '#090c0f', 1)
        lamp(802, 156, self.mode == 'TX', '#ff5959')
        text(816, 145, 72, 22, 'TX', 8, '#aab4bf')
        lamp(876, 156, self.mode == 'RX', '#6fef6c')
        text(890, 145, 50, 22, 'RX', 8, '#aab4bf')
        knob(864, 248, 70, 'DISPLAY ONLY')
        # Printed key legends mimic the hardware; actual connection buttons sit below.
        for x, title in [(128, 'MENU'), (252, 'FUNCTION'), (376, 'M.SCOPE'), (500, 'QUICK'), (624, 'EXIT')]:
            rect(x, 358, 108, 25, '#252a2e', 3, '#444b52')
            text(x, 358, 108, 25, title, 8, '#c4cbd2', True, Qt.AlignCenter)
        text(787, 358, 155, 25, 'IC-705 INSPIRED', 8, '#8a959f', False, Qt.AlignCenter)
        p.end()
