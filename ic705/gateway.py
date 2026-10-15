# SPDX-License-Identifier: GPL-3.0-or-later
"""USB-only, single-reflector bridge. No CI-V or computer audio required."""
import random
import time
from PySide6.QtCore import QObject, QTimer, Signal
from .dstar.dplus import DPlusAuthenticator, DPlusLink
from .dstar.icom_terminal import IcomTerminal
from .dstar.protocol import Header, END_PATTERN_BYTES, pad

PRESETS = {'REF030C': 'REF030 C', 'REF001C': 'REF001 C'}


def validate_call(call):
    import re
    call = call.upper().strip()
    if not re.fullmatch(r'[A-Z0-9]{3,7}', call) or not any(c.isdigit() for c in call) or not any(c.isalpha() for c in call):
        raise ValueError('Enter your base amateur callsign (3–7 letters/digits), without a /suffix.')
    return call


class Gateway(QObject):
    log = Signal(str)
    radio_status = Signal(bool)
    network_status = Signal(str)
    activity = Signal(str)

    def __init__(self, login, module, port):
        super().__init__()
        self.login = validate_call(login)
        self.terminal_call = pad(login)[:7] + module
        self.gateway_call = pad(login)[:7] + 'G'
        self.terminal = IcomTerminal(port)
        self.terminal.setParent(self)
        self.terminal.log.connect(self.log)
        self.terminal.connected.connect(self._radio_status)
        self.terminal.header_received.connect(self._radio_header)
        self.terminal.data_received.connect(self._radio_data)
        self.auth = DPlusAuthenticator(login)
        self.auth.setParent(self)
        self.auth.log.connect(self.log)
        self.auth.done.connect(self._auth_done)
        self.link = None
        self.selected = ''
        self.pending = False
        self.active = False
        self.tx_id = 0
        self.tx_seq = 0
        self.tx_seen = 0.0
        self.rx_id = None
        self.rx_expected = None
        self.radio_tx = False
        self.watchdog = QTimer(self, interval=200)
        self.watchdog.timeout.connect(self._watch)
        self.rx_seen = 0.0
        self.link_deadline = QTimer(self, singleShot=True, interval=25000)
        self.link_deadline.timeout.connect(self._link_timeout)

    def start(self, preset):
        self.active = True
        self.selected = PRESETS[preset]
        self.pending = True
        self.network_status.emit('Waiting for radio and D-Plus directory')
        self.terminal.open()
        self.auth.start()
        self.watchdog.start()

    def stop(self):
        self.active = False
        self.pending = False
        self.watchdog.stop()
        self.link_deadline.stop()
        self.auth.timer.stop()
        self._end_tx()
        self._end_rx()
        if self.link:
            self.link.close()
            self.link.deleteLater()
            self.link = None
        self.terminal.close()
        self.network_status.emit('Disconnected')
        self.activity.emit('Idle')

    def _radio_status(self, connected):
        self.radio_status.emit(connected)
        if connected:
            self._maybe_link()
        else:
            self._end_tx()
            self.radio_tx = False
            self.rx_id = None
            if self.link:
                self.link.close()
                self.link.deleteLater()
                self.link = None
            self.link_deadline.stop()
            if self.active:
                self.pending = True
                self.network_status.emit('Waiting for USB radio')
            self.activity.emit('Idle')

    def _auth_done(self, ok, hosts):
        if not self.active:
            return
        if not ok:
            self.network_status.emit('D-Plus directory failed — disconnect and retry')
            self.pending = False
            return
        self._maybe_link()

    def _maybe_link(self):
        if not (self.active and self.pending and self.terminal.is_connected and self.auth.authenticated_at):
            return
        host = self.auth.hosts.get(self.selected[:6])
        if not host:
            self.pending = False
            self.network_status.emit('Reflector not in D-Plus directory — retry later')
            self.log.emit('No address was returned for ' + self.selected[:6])
            return
        # The directory normally supplies numeric IPv4 addresses. No DNS on the GUI thread.
        import ipaddress
        try:
            ipaddress.IPv4Address(host)
        except ValueError:
            self.pending = False
            self.network_status.emit('Directory returned an invalid IPv4 address')
            return
        self.pending = False
        self.link = DPlusLink(self.selected, host, self.login, self.terminal_call)
        self.link.setParent(self)
        self.link.log.connect(self.log)
        self.link.state_changed.connect(self._link_state)
        self.link.header_received.connect(self._net_header)
        self.link.data_received.connect(self._net_data)
        self.link_deadline.start()
        self.link.link()

    def _link_state(self, state):
        if state == 'linked':
            self.link_deadline.stop()
            self.network_status.emit(self.selected.replace(' ', '') + ' — reflector accepted link')
        elif state == 'linking':
            self._end_tx()
            self._end_rx()
            self.network_status.emit('Linking ' + self.selected.replace(' ', ''))
            if not self.link_deadline.isActive():
                self.link_deadline.start()
        else:
            self.link_deadline.stop()
            self._end_tx()
            self._end_rx()
            self.network_status.emit('Reflector ' + state + ' — disconnect and retry')

    def _link_timeout(self):
        if self.link and self.link.state != 'linked':
            self.link.close()
            self.network_status.emit('No reflector reply — disconnect and retry')
            self.log.emit('Link timed out after 25 seconds. Check registration, Internet and firewall.')

    def _radio_header(self, header):
        self._end_rx()
        # Drop queued inbound audio as soon as the user presses radio PTT.
        self.terminal.cancel_output()
        self._end_tx()
        self.radio_tx = True
        self.tx_seen = time.monotonic()
        if header.my.strip().upper() != self.login:
            self.log.emit('TX ignored: radio MY callsign differs from the app callsign.')
            return
        if header.your.strip() != 'CQCQCQ':
            self.log.emit('TX ignored: set radio TO/UR to CQCQCQ for voice.')
            return
        if self.link and self.link.state == 'linked':
            self.tx_id = random.randint(1, 65535)
            self.tx_seq = 0
            self.link.send_header(self.tx_id, header.with_(your=pad('CQCQCQ')))
            self.activity.emit('TX • ' + self.login)
            self.log.emit('TX to ' + self.selected.replace(' ', ''))
        else:
            self.log.emit('TX ignored: no reflector link.')

    def _radio_data(self, frame, end):
        self.tx_seen = time.monotonic()
        end = end or frame[:6] == END_PATTERN_BYTES[:6]
        if self.tx_id and self.link and self.link.state == 'linked':
            self.link.send_data(self.tx_id, self.tx_seq, frame, end)
            self.tx_seq = (self.tx_seq + 1) % 21
            if end:
                self.tx_id = 0
        if end:
            self.radio_tx = False
            self.activity.emit('Idle')

    def _net_header(self, stream_id, header):
        if not (self.active and self.terminal.is_connected and self.link and self.link.state == 'linked'):
            return
        if self.radio_tx or self.rx_id is not None:
            return
        # D-Plus dongle links can carry several modules; receive ONLY selected C.
        if self.selected not in (pad(header.rpt1), pad(header.rpt2)):
            return
        self.rx_id = stream_id
        self.rx_expected = None
        self.rx_seen = time.monotonic()
        self.terminal.write_header(Header(rpt2=self.terminal_call, rpt1=self.gateway_call,
                                         your=pad('CQCQCQ'), my=header.my, my2=header.my2))
        self.activity.emit('RX • ' + header.my.strip())
        self.log.emit('RX ' + header.describe())

    def _net_data(self, stream_id, seq, frame, end):
        if stream_id != self.rx_id or self.rx_id is None:
            return
        if not end:
            if not 0 <= seq <= 20:
                return
            if self.rx_expected is not None:
                delta = (seq - self.rx_expected) % 21
                if delta > 10:
                    return  # duplicate or late UDP packet
                if delta:
                    self.log.emit(f'RX: {delta} voice frame(s) lost on the Internet.')
            self.rx_expected = (seq + 1) % 21
        self.rx_seen = time.monotonic()
        if end:
            self._end_rx()
        else:
            self.terminal.write_data(frame)

    def _end_tx(self):
        if self.tx_id and self.link and self.link.state == 'linked':
            self.link.send_data(self.tx_id, self.tx_seq, b'', end=True)
        self.tx_id = 0

    def _end_rx(self):
        if self.rx_id is not None:
            self.terminal.write_data(b'', end=True)
            self.rx_id = None
            self.rx_expected = None
            self.activity.emit('Idle')

    def _watch(self):
        now = time.monotonic()
        if self.rx_id is not None and now - self.rx_seen > 1.0:
            self.log.emit('RX stream ended after network timeout.')
            self._end_rx()
        if self.radio_tx and now - self.tx_seen > 1.0:
            self.log.emit('TX stream ended after USB timeout.')
            self._end_tx()
            self.radio_tx = False
            self.activity.emit('Idle')
