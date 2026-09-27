"""Persistent HiChip PPPP client for local GF-L300 floodlight control.

Keeps one authenticated LAN session warm (like the vendor app) so on/off
commands are near-instant. A background thread handles keep-alives and acks;
`send()` just emits the command on the live session.
"""
from __future__ import annotations

import logging
import socket
import struct
import threading
import time

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PORTS = (32108, 10000, 32100)
KEEPALIVE_S = 1.5
IDLE_RECONNECT_S = 12.0   # if no packet heard this long, session is considered dead


class HiChipError(Exception):
    """Camera unreachable or session refused."""


class HiChipFloodlight:
    def __init__(self, host, uid, setup, cmd_on, cmd_off, cmd_auto, timeout=1.0):
        self._host = host
        self._uid = uid
        self._setup = setup
        self._cmds = {"on": cmd_on, "off": cmd_off, "auto": cmd_auto}
        self._timeout = timeout
        self._sock: socket.socket | None = None
        self._dst = None
        self._seq = 0
        self._connected = False
        self._last_rx = 0.0
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- framing -----------------------------------------------------------
    @staticmethod
    def _drw(seq, payload):
        body = b"\xd1\x00" + struct.pack(">H", seq) + payload
        return b"\xf1\xd0" + struct.pack(">H", len(body)) + body

    def _ack(self, seq_bytes):
        self._sock.sendto(b"\xf1\xd1\x00\x06\xd1\x00\x00\x01" + seq_bytes, self._dst)

    # -- session -----------------------------------------------------------
    def _discover(self, sock):
        for port in DISCOVERY_PORTS:
            try:
                sock.sendto(bytes([0xF1, 0x30, 0, 0]), (self._host, port))
                data, addr = sock.recvfrom(2048)
                if data[:2] == b"\xf1\x41":
                    return addr[1]
            except socket.timeout:
                continue
        raise HiChipError(f"no PPPP reply from {self._host}")

    def _read_for(self, secs, want=None):
        end = time.time() + secs
        got = None
        while time.time() < end:
            try:
                data, _ = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            self._last_rx = time.time()
            if data[1] == 0xD0:
                self._ack(data[6:8])
                if want is not None and data[8:12] == b"\x99\x99\x99\x99" \
                        and struct.unpack("<H", data[16:18])[0] == want:
                    got = data
        return got

    def _connect(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self._timeout)
        self._sock = sock
        port = self._discover(sock)
        self._dst = (self._host, port)
        for _ in range(3):
            sock.sendto(b"\xf1\x41\x00\x14" + self._uid, self._dst)
        self._read_for(0.5)
        sock.sendto(b"\xf1\xe0\x00\x00", self._dst)
        self._read_for(0.2)
        for seq, payload in enumerate(self._setup):
            sock.sendto(self._drw(seq, payload), self._dst)
            self._read_for(0.2)
        self._seq = len(self._setup)
        self._connected = True
        self._last_rx = time.time()
        _LOGGER.debug("HiChip session established with %s", self._dst)

    def _ensure(self):
        if not self._connected or (time.time() - self._last_rx) > IDLE_RECONNECT_S:
            self._connect()

    # -- background keepalive ---------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        with self._lock:
            self._connected = False
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                with self._lock:
                    self._ensure()
                    self._sock.sendto(b"\xf1\xe0\x00\x00", self._dst)
                self._read_for(KEEPALIVE_S)     # acks camera DRWs, updates _last_rx
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("keepalive: %s", err)
                with self._lock:
                    self._connected = False
                self._stop.wait(2.0)

    # -- public ------------------------------------------------------------
    def send(self, command):
        if command not in self._cmds:
            raise ValueError(command)
        with self._lock:
            self._ensure()
            seq = self._seq
            self._seq += 1
            self._sock.sendto(self._drw(seq, self._cmds[command]), self._dst)
        # optimistic; the keepalive loop will ack the camera's response

    def test_connection(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self._timeout)
        try:
            self._discover(sock)
            return True
        finally:
            sock.close()
