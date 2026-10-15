# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import sys
from pathlib import Path
from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QPlainTextEdit,
    QVBoxLayout, QWidget, QCheckBox)
from .gateway import Gateway, validate_call
from .frontpanel import FrontPanel


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('HamTec • IC-705 Reflector Link 0.2')
        self.resize(1080, 860)
        self.setMinimumSize(900, 760)
        self.settings = QSettings('HamTec', 'IC705ReflectorLink')
        self.gateway = None
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(10)
        self.panel = FrontPanel()
        layout.addWidget(self.panel, 4)
        # Real connection controls, separate from the painted faceplate.
        buttons = QHBoxLayout()
        self.ref30 = QPushButton('Connect REF030C')
        self.ref1 = QPushButton('Connect REF001C')
        self.disconnect = QPushButton('Disconnect')
        self.disconnect.setEnabled(False)
        self.ref30.setObjectName('connectButton')
        self.ref1.setObjectName('connectButton')
        self.disconnect.setObjectName('disconnectButton')
        self.ref30.clicked.connect(lambda: self.connect_to('REF030C'))
        self.ref1.clicked.connect(lambda: self.connect_to('REF001C'))
        self.disconnect.clicked.connect(self.stop)
        for button in (self.ref30, self.ref1, self.disconnect):
            button.setMinimumHeight(42)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.call = QLineEdit(str(self.settings.value('call', '')))
        self.call.setPlaceholderText('Registered callsign')
        self.call.setMaxLength(7)
        self.call.textChanged.connect(lambda value: self.set_panel_call(value))
        self.panel.local_call = self.call.text().strip().upper()
        self.module = QComboBox()
        self.module.addItems(list('ABCDEFIJKLMNOPQRSTUVWXYZ'))
        self.module.setCurrentText(str(self.settings.value('module', 'B')))
        self.ports = QComboBox()
        self.ports.setEditable(True)
        self.ports.setMinimumWidth(210)
        self.refresh = QPushButton('Refresh')
        self.refresh.clicked.connect(self.scan)
        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel('MY'))
        settings_row.addWidget(self.call, 2)
        settings_row.addWidget(QLabel('Terminal module'))
        settings_row.addWidget(self.module)
        settings_row.addWidget(QLabel('USB data'))
        settings_row.addWidget(self.ports, 3)
        settings_row.addWidget(self.refresh)
        layout.addLayout(settings_row)
        hint = QLabel('Use the radio microphone / PTT. Match the Terminal/AP module on your IC-705. The on-screen meter is simulated.')
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        layout.addWidget(hint)
        status = QHBoxLayout()
        self.radio = QLabel('USB radio: disconnected')
        self.network = QLabel('Network: disconnected')
        self.network.setWordWrap(True)
        self.activity = QLabel('Idle')
        self.activity.setMinimumWidth(120)
        self.activity.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.activity.setObjectName('activity')
        status.addWidget(self.radio, 2)
        status.addWidget(self.network, 4)
        status.addWidget(self.activity, 1)
        layout.addLayout(status)
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(600)
        self.logbox.setMinimumHeight(95)
        layout.addWidget(self.logbox, 1)
        footer = QHBoxLayout()
        help_button = QPushButton('Radio setup / Help')
        help_button.clicked.connect(self.show_help)
        python_button = QPushButton('Python 3.13 download')
        python_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://www.python.org/ftp/python/3.13.16/python-3.13.16-amd64.exe')))
        about_button = QPushButton('About')
        about_button.clicked.connect(self.about)
        self.meter_toggle = QCheckBox('Animate simulated meter')
        enabled = str(self.settings.value('animate_meter', 'true')).lower() == 'true'
        self.meter_toggle.setChecked(enabled)
        self.panel.set_animation(enabled)
        self.meter_toggle.toggled.connect(self.toggle_meter)
        footer.addWidget(help_button)
        footer.addWidget(python_button)
        footer.addStretch()
        footer.addWidget(self.meter_toggle)
        footer.addWidget(about_button)
        layout.addLayout(footer)
        self.scan()
        saved = str(self.settings.value('port', ''))
        if saved:
            i = self.ports.findData(saved)
            if i >= 0:
                self.ports.setCurrentIndex(i)
            else:
                self.ports.setEditText(saved)
        self.append_log('Ready. IC-705-inspired panel • RX/TX follows DV streams • meter and trace are simulated.')

    def set_panel_call(self, value):
        self.panel.local_call = value.strip().upper()
        self.panel.update()

    def toggle_meter(self, enabled):
        self.settings.setValue('animate_meter', 'true' if enabled else 'false')
        self.panel.set_animation(enabled)

    def update_radio(self, ok):
        self.radio.setText('USB radio: ' + ('responding' if ok else 'not responding'))
        self.panel.set_radio(ok)

    def update_network(self, state):
        self.network.setText('Network: ' + state)
        self.panel.set_network(state)

    def update_activity(self, state):
        self.activity.setText(state)
        self.panel.set_activity(state)
        color = '#ff7676' if state.startswith('TX') else '#8bf390' if state.startswith('RX') else '#a7bbc9'
        self.activity.setStyleSheet('font-weight: bold; color: ' + color)

    def scan(self):
        self.ports.clear()
        ports = sorted(QSerialPortInfo.availablePorts(), key=lambda p: p.portName())
        for port in ports:
            self.ports.addItem(f'{port.portName()} — {port.description()}', port.portName())
        # Suggest only when exactly one Icom radio exposes two interfaces.
        icom = [p for p in ports if p.vendorIdentifier() == 0x0C26]
        if len(icom) == 2:
            import re
            icom.sort(key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', p.portName())])
            self.ports.setCurrentIndex(self.ports.findData(icom[-1].portName()))
        elif not ports:
            self.ports.setEditText('')

    def append_log(self, text):
        from datetime import datetime
        self.logbox.appendPlainText(datetime.now().strftime('%H:%M:%S  ') + text)
        logging.info(text)

    def connect_to(self, preset):
        try:
            call = validate_call(self.call.text())
        except ValueError as exc:
            QMessageBox.warning(self, 'Callsign needed', str(exc))
            return
        port = self.ports.currentData() if self.ports.currentIndex() >= 0 else None
        # Editable combobox text is authoritative if the user typed a bare port.
        if self.ports.currentText() != self.ports.itemText(self.ports.currentIndex()):
            port = self.ports.currentText().strip()
        if not port:
            QMessageBox.warning(self, 'USB port needed', 'Connect the radio USB cable, click Refresh, and select the data COM port.')
            return
        self.stop()
        self.call.setText(call)
        self.settings.setValue('call', call)
        self.settings.setValue('port', port)
        self.settings.setValue('module', self.module.currentText())
        self.gateway = Gateway(call, self.module.currentText(), port)
        self.gateway.log.connect(self.append_log)
        self.gateway.radio_status.connect(self.update_radio)
        self.gateway.network_status.connect(self.update_network)
        self.gateway.activity.connect(self.update_activity)
        self.panel.reflector = preset
        self.panel.update()
        self.append_log('Selected ' + preset + '. Network linking waits for the USB radio response.')
        for control in (self.call, self.module, self.ports, self.refresh):
            control.setEnabled(False)
        self.disconnect.setEnabled(True)
        self.gateway.start(preset)

    def stop(self):
        if self.gateway:
            old, self.gateway = self.gateway, None
            old.stop()
            old.deleteLater()
            self.append_log('Disconnected.')
        for control in (self.call, self.module, self.ports, self.refresh):
            control.setEnabled(True)
        self.disconnect.setEnabled(False)
        self.radio.setText('USB radio: disconnected')
        self.network.setText('Network: disconnected')
        self.update_activity('Idle')
        self.panel.set_radio(False)
        self.panel.set_network('Disconnected')

    def show_help(self):
        QMessageBox.information(self, 'Radio setup',
            '1. Install the official Icom IC-705 USB driver and connect a USB DATA cable.\n\n'
            '2. Set your MY callsign on the radio. Use the same base callsign here.\n\n'
            '3. MENU > 2 > DV GW > Gateway Select > External Gateway (USB (B)). '
            'Set Terminal/AP Call Sign to your base callsign padded to 7 positions plus the module '
            'shown here (default B), then select <<Terminal Mode>>.\n\n'
            '4. Set TO/UR to CQCQCQ. Close RS-MS3W, Doozy and any app using the data COM port.\n\n'
            '5. Select the data COM port here and click a reflector button. Once linked, '
            'listen on the radio and use the radio microphone/PTT to talk. '
            'Only module C audio is passed to the radio.\n\n'
            'REF001 and REF030 require D-STAR US Trust registration. A network link does '
            'not prove your transmitted audio will be accepted. See README.html for details.')

    def about(self):
        QMessageBox.information(self, 'About IC-705 Reflector Link',
            'IC-705 Reflector Link 0.2.0 — IC-705-inspired front panel.\n\n'
            'USB and D-Plus components adapted from QDStar by Manuel Alcocer Jiménez (EA7KLX), '
            'derived from G4KLX DStarRepeater / ircDDBGateway. GPL-3.0-or-later; source included.\n\n'
            'RX/TX lights follow actual gateway DV streams. S-meter, trace and knobs are decorative; '
            'no RF signal strength is measured.\n\n'
            'No warranty. Not affiliated with Icom. Tested with simulated peers; '
            'not tested with a physical IC-705 or live reflector.\n\n'
            'See LICENSE and THIRD_PARTY.md in the application folder.')

    def closeEvent(self, event):
        self.stop()
        event.accept()


def configure_appearance(app):
    app.setStyle('Fusion')
    app.setFont(QFont('Segoe UI', 10))
    app.setStyleSheet('''
        QWidget { background: #12171d; color: #e8eff8; }
        QLabel#muted { color: #95a8bb; font-size: 12px; }
        QPushButton#connectButton { background: #164a65; border: 1px solid #3c8aa5; font-weight: bold; }
        QPushButton#connectButton:hover { background: #216784; }
        QPushButton#disconnectButton { background: #533334; border-color: #8e5658; }
        QPushButton#disconnectButton:disabled { color: #6b7b88; background: #202932; border-color: #39434c; }
        QLineEdit, QComboBox, QPlainTextEdit { background: #1d2b3d; border: 1px solid #364962; border-radius: 5px; padding: 7px; }
        QPushButton { background: #224c6f; border: 1px solid #407499; border-radius: 5px; padding: 8px; }
        QPushButton:hover { background: #2a618c; }
        QPushButton:disabled { color: #798b9e; background: #253243; border-color: #364254; }
        QPlainTextEdit { font-family: Consolas, monospace; font-size: 12px; }
    ''')


def main():
    app = QApplication(sys.argv)
    configure_appearance(app)
    logdir = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'HamTec' / 'IC705ReflectorLink'
    logdir.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    handler = RotatingFileHandler(logdir / 'app.log', maxBytes=1000000, backupCount=2, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', handlers=[handler])
    def report_error(kind, value, tb):
        logging.error('Unhandled error', exc_info=(kind, value, tb))
        QMessageBox.critical(None, 'Application error', str(value) + '\n\nDetails are in ' + str(logdir / 'app.log'))
    sys.excepthook = report_error
    window = Window()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
