# IC-705 Reflector Link 0.2.0 — third-party notices

This is a modified, reduced USB-only application, not an official QDStar or Icom release.
Distributed under GPL-3.0-or-later. The complete source for this application is included.
See LICENSE for the GPL terms and warranty disclaimer.

## QDStar

Author: Manuel Alcocer Jiménez, EA7KLX.
Source: https://github.com/manuel-alcocer/qdstar
Reference commit: 0248b028e4df0d4eaac1bf13866fa84113ff5e0a
License: GPL-3.0-or-later.

The files ic705/dstar/icom_terminal.py, dplus.py and protocol.py are adapted
from QDStar's qdstar/dstar files. The gateway routing is adapted from its core.py.
Modifications dated 2026-10-15 include: a USB-only two-preset GUI; module-C
receive filtering; callsign validation; stricter packet validation and peer
checking; bounded audio queues; direct UDP sockets; explicit timeouts and
stream cleanup; and offline tests. No WLAN credentials or telemetry are used.

QDStar identifies its Terminal Mode and DPlus implementations as ports of:
- Jonathan Naylor, G4KLX: DStarRepeater CIcomController and ircDDBGateway
  CDPlusAuthenticator / CDPlusHandler / CDPlusProtocolHandler.
- https://github.com/g4klx/DStarRepeater
- https://github.com/g4klx/ircDDBGateway
- GPL version 2 or later; combined derivative distributed under GPL 3 or later.
- Icom controller original copyright (C) 2011–2015, 2018, 2019 Jonathan Naylor.

## Runtime dependencies (downloaded separately by SETUP.cmd)

Python: Python Software Foundation license, https://docs.python.org/3/license.html
PySide6 / Shiboken6 / Qt 6.8.3: Qt for Python; LGPLv3/GPLv3/commercial options,
with individual module notices in the installed distributions.
https://doc.qt.io/qtforpython-6/licenses.html
https://code.qt.io/cgit/pyside/pyside-setup.git/
https://code.qt.io/cgit/qt/

The source download does not bundle those runtimes. An optional Windows build
uses PyInstaller 6.12.0 (GPL with bootloader exception). Keep its included Qt
license files and shared libraries; supply corresponding source/license
materials as required by their licenses when redistributing binaries.
https://pyinstaller.org/en/stable/license.html

Icom, IC-705 and D-STAR names identify compatible equipment/protocols.
This software is not endorsed by or affiliated with Icom.

Version 0.2 adds an original QPainter front panel, actual DV RX/TX indicators,
a clearly labelled simulated S-meter/trace, and an animation toggle.
