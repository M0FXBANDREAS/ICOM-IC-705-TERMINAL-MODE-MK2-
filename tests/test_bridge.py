# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline tests: local fake reflector only; no Internet or radio needed."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import struct
import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import QByteArray
from PySide6.QtNetwork import QHostAddress, QUdpSocket
from PySide6.QtWidgets import QApplication
from ic705.dstar.protocol import Header, ccitt_crc, pad, NULL_FRAME, SYNC_FRAME
from ic705.dstar.icom_terminal import IcomTerminal
from ic705.dstar.dplus import DPlusLink, authenticate
from ic705.gateway import Gateway, validate_call
APP = QApplication.instance() or QApplication([])


def process_until(condition):
    end = time.monotonic() + 1
    while time.monotonic() < end:
        APP.processEvents()
        if condition(): return
        time.sleep(.002)
    raise AssertionError('Local event timeout')


class FakeSerial:
    def __init__(self): self.input, self.output, self.open = b'', [], True
    def readAll(self):
        data, self.input = self.input, b''
        return QByteArray(data)
    def write(self, data): self.output.append(bytes(data)); return len(data)
    def isOpen(self): return self.open
    def close(self): self.open = False


class TestProtocol(unittest.TestCase):
    def test_crc_and_header(self):
        self.assertEqual(ccitt_crc(b'123456789'), b'\x6e\x90')
        h = Header(rpt1='REF030 C', my=pad('M0ABC'), my2='705 ')
        self.assertEqual(len(h.to_radio()), 41)
        self.assertEqual(Header.from_radio(h.to_radio()), h)

    def test_callsign(self):
        self.assertEqual(validate_call('m0abc'), 'M0ABC')
        for s in ['TEST', '12345', 'M0ABC/P', 'M0ABC;X', '', '12345678']:
            with self.assertRaises(ValueError): validate_call(s)

    def test_usb_fragmentation_ack_and_end(self):
        t = IcomTerminal('TEST')
        t.serial.deleteLater()
        t.serial = FakeSerial()
        received = []
        t.header_received.connect(received.append)
        h = Header(my=pad('M0ABC'))
        wire = b'\x2c\x10' + h.to_radio() + b'\xff'
        for b in b'\xff\xff\xaa' + wire:
            t.serial.input = bytes([b]); t._read()
        self.assertEqual(received, [h])
        t.write_header(h)
        self.assertEqual(len(t.serial.output[-1]), 42)
        t.write_data(SYNC_FRAME)
        self.assertEqual(len(t.tx_queue), 1)
        t._handle(b'\x03\x21\x00')
        self.assertEqual(t.serial.output[-1][:4], b'\x10\x22\x00\x00')
        t._handle(b'\x04\x23\x00\x00')
        self.assertIsNone(t.in_flight)
        t.write_data(NULL_FRAME)
        t._handle(b'\x04\x23\x00\x00')
        self.assertIsNotNone(t.in_flight)
        t._handle(b'\x04\x23\x01\x00')
        t.write_data(b'', True)
        self.assertTrue(t.serial.output[-1][3] & 0x40)
        t.close()
        self.assertIsNone(t.in_flight)
        self.assertEqual(len(t.tx_queue), 0)

    def test_header_crc_and_handshake_validation(self):
        link = DPlusLink('REF030 C', '127.0.0.1', 'M0ABC', 'M0ABC  B')
        events = []
        link.header_received.connect(lambda *x: events.append(x))
        for p in [b'', b'DSVT', b'\x08\xff\x04\x00OKRW', b'\x3a\x80DSVT']:
            link._handle(p)
        self.assertNotEqual(link.state, 'linked')
        link._set_state('linked')
        h = Header(rpt1='REF030 C', my=pad('M1XYZ'))
        raw = b'\x3a\x80DSVT\x10\x00\x00\x00\x20\x00\x00\x00' + struct.pack('<H', 123) + b'\x80' + h.to_radio()
        link._handle(raw[:-1] + bytes([raw[-1] ^ 1]))
        self.assertEqual(events, [])
        link._handle(raw)
        self.assertEqual(events, [(123, h)])
        link.close()

    def test_real_local_udp_handshake_and_voice(self):
        server = QUdpSocket()
        self.assertTrue(server.bind(QHostAddress('127.0.0.1'), 20001))
        link = DPlusLink('REF030 C', '127.0.0.1', 'M0ABC', 'M0ABC  B')
        try:
            link.link(); process_until(server.hasPendingDatagrams)
            d = server.receiveDatagram()
            self.assertEqual(bytes(d.data()), b'\x05\x00\x18\x00\x01')
            address, port = d.senderAddress(), d.senderPort()
            server.writeDatagram(d.data(), address, port)
            process_until(server.hasPendingDatagrams)
            identity = bytes(server.receiveDatagram().data())
            self.assertEqual(identity[:4], b'\x1c\xc0\x04\x00')
            self.assertEqual(identity[4:9], b'M0ABC')
            server.writeDatagram(b'\x08\xc0\x04\x00OKRW', address, port)
            process_until(lambda: link.state == 'linked')
            link.send_header(4321, Header(my=pad('M0ABC')))
            process_until(server.hasPendingDatagrams)
            header = bytes(server.receiveDatagram().data())
            self.assertEqual(len(header), 58)
            parsed = Header.from_radio(header[17:])
            self.assertEqual(parsed.rpt2, 'REF030 C')
            self.assertEqual(parsed.rpt1, 'M0ABC  B')
            while server.hasPendingDatagrams(): server.receiveDatagram()
            link.send_data(4321, 0, SYNC_FRAME)
            process_until(server.hasPendingDatagrams)
            self.assertEqual(len(bytes(server.receiveDatagram().data())), 29)
            link.send_data(4321, 1, b'', True)
            process_until(server.hasPendingDatagrams)
            end = bytes(server.receiveDatagram().data())
            self.assertEqual(len(end), 32)
            self.assertEqual(end[16], 0x41)
        finally:
            link.close(); server.close()

    def test_directory_and_invalid_length(self):
        class Stream:
            def __init__(self, data): self.data, self.sent = data, b''
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def sendall(self, data): self.sent = data
            def recv(self, n):
                chunk, self.data = self.data[:n], self.data[n:]
                return chunk
        record = b'127.0.0.1'.ljust(16, b'\x00') + b'REF030  ' + b'\x00\x80'
        stream = Stream(bytes([34, 0xc0, 1, 0, 0, 0, 0, 0]) + record)
        with patch('socket.create_connection', return_value=stream):
            self.assertEqual(authenticate('M0ABC'), {'REF030': '127.0.0.1'})
        self.assertEqual(len(stream.sent), 56)
        self.assertEqual(stream.sent[4:9], b'M0ABC')
        with patch('socket.create_connection', return_value=Stream(b'\x01\xc0')):
            with self.assertRaises(OSError): authenticate('M0ABC')

    def test_module_filter_half_duplex_timeout(self):
        g = Gateway('M0ABC', 'B', 'TEST')
        g.active, g.selected, g.terminal.is_connected = True, 'REF030 C', True
        class Link:
            state = 'linked'
            def __init__(self): self.headers, self.frames = [], []
            def send_header(self, *a): self.headers.append(a)
            def send_data(self, *a, **k): self.frames.append((a, k))
            def close(self): pass
            def deleteLater(self): pass
        g.link = Link()
        headers, frames = [], []
        g.terminal.write_header = headers.append
        g.terminal.write_data = lambda *a, **k: frames.append((a, k))
        h = Header(rpt1='REF030 B', my=pad('M1XYZ'))
        g._net_header(100, h)
        self.assertIsNone(g.rx_id)
        g._net_header(101, h.with_(rpt1='REF030 C'))
        g._net_header(101, h.with_(rpt1='REF030 C'))
        self.assertEqual(len(headers), 1)
        g._net_data(101, 0, SYNC_FRAME, False)
        g._net_data(101, 0, SYNC_FRAME, False)
        g._net_data(102, 1, NULL_FRAME, False)
        self.assertEqual(len(frames), 1)
        g._radio_header(Header(my=pad('M0ABC')))
        self.assertIsNone(g.rx_id)
        self.assertEqual(len(g.link.headers), 1)
        g._net_header(103, h.with_(rpt1='REF030 C'))
        self.assertIsNone(g.rx_id)
        g._radio_data(SYNC_FRAME, False)
        g._radio_data(b'', True)
        self.assertFalse(g.radio_tx)
        self.assertEqual(g.tx_id, 0)
        g._net_header(104, h.with_(rpt1='REF030 C'))
        g.rx_seen = time.monotonic() - 2
        g._watch()
        self.assertIsNone(g.rx_id)
        g.stop()

    def test_gui(self):
        from ic705.__main__ import Window, configure_appearance
        configure_appearance(APP)
        window = Window()
        self.assertEqual(window.ref30.text(), 'Connect REF030C')
        self.assertEqual(window.ref1.text(), 'Connect REF001C')
        self.assertFalse(window.disconnect.isEnabled())
        window.update_radio(True)
        window.update_network('REF030C — reflector accepted link')
        window.update_activity('RX • DEMO')
        for _ in range(10): window.panel.tick()
        self.assertTrue(window.panel.radio_ok)
        self.assertTrue(window.panel.linked)
        self.assertEqual(window.panel.mode, 'RX')
        self.assertGreater(window.panel.level, 0)
        window.update_activity('TX • DEMO')
        self.assertEqual(window.panel.mode, 'TX')
        window.update_activity('Idle')
        self.assertEqual(window.panel.level, 0)
        window.show(); APP.processEvents()
        window.grab().save('preview.png')
        window.close()


if __name__ == '__main__': unittest.main(verbosity=2)
