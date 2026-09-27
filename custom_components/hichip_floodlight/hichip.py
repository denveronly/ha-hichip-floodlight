"""Minimal HiChip PPPP client for local GF-L300 floodlight control.

The camera speaks HiChip's PPPP protocol over UDP on the LAN. This client
establishes a session, replays the (deterministic, per-device) login and
485-light-module setup payloads captured for the camera, and then sends the
floodlight on/off/auto command. All bytes are device-specific constants stored
in the config entry (the "camera profile"); nothing here is secret beyond the
camera password that was baked into the captured login payload.
"""
from __future__ import annotations

import logging
import socket
import struct
import time

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PORTS = (32108, 10000, 32100)


class HiChipError(Exception):
    """Raised when the camera cannot be reached or refuses the session."""


class HiChipFloodlight:
    """Talks to one GF-L300-style HiChip camera on the LAN."""

    def __init__(self, host: str, uid: bytes, setup: list[bytes],
                 cmd_on: bytes, cmd_off: bytes, cmd_auto: bytes,
                 timeout: float = 1.2) -> None:
        self._host = host
        self._uid = uid                      # 20-byte PPPP UID field
        self._setup = setup                  # login + 485 setup app-payloads
        self._cmds = {"on": cmd_on, "off": cmd_off, "auto": cmd_auto}
        self._timeout = timeout

    # -- low level ---------------------------------------------------------
    def _discover_port(self, sock: socket.socket) -> int:
        for port in DISCOVERY_PORTS:
            try:
                sock.sendto(bytes([0xF1, 0x30, 0x00, 0x00]), (self._host, port))
                data, addr = sock.recvfrom(2048)
                if data[:2] == b"\xf1\x41":
                    return addr[1]
            except socket.timeout:
                continue
        raise HiChipError(f"no PPPP reply from {self._host}")

    @staticmethod
    def _drw(seq: int, payload: bytes) -> bytes:
        # F1 D0 <len16 BE> D1 00 <seq16 BE> <payload>
        body = b"\xd1\x00" + struct.pack(">H", seq) + payload
        return b"\xf1\xd0" + struct.pack(">H", len(body)) + body

    def _ack(self, sock, dst, seq_bytes: bytes) -> None:
        sock.sendto(b"\xf1\xd1\x00\x06\xd1\x00\x00\x01" + seq_bytes, dst)

    def _drain(self, sock, dst, secs: float, want: int | None = None):
        end = time.time() + secs
        got = None
        while time.time() < end:
            try:
                data, _ = sock.recvfrom(2048)
            except socket.timeout:
                continue
            if data[1] == 0xD0:                      # camera DRW -> ack it
                self._ack(sock, dst, data[6:8])
                if data[8:12] == b"\x99\x99\x99\x99" and len(data) >= 18:
                    io = struct.unpack("<H", data[16:18])[0]
                    if want is not None and io == want:
                        got = data
        return got

    # -- public ------------------------------------------------------------
    def send(self, command: str) -> None:
        """Establish a session and send 'on' | 'off' | 'auto'."""
        if command not in self._cmds:
            raise ValueError(command)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self._timeout)
        try:
            port = self._discover_port(sock)
            dst = (self._host, port)
            # handshake
            for _ in range(3):
                sock.sendto(b"\xf1\x41\x00\x14" + self._uid, dst)
            self._drain(sock, dst, 0.8)
            sock.sendto(b"\xf1\xe0\x00\x00", dst)
            self._drain(sock, dst, 0.6)
            # replay login + 485 setup (seq 0..5)
            for seq, payload in enumerate(self._setup):
                sock.sendto(self._drw(seq, payload), dst)
                self._drain(sock, dst, 0.8)
            sock.sendto(b"\xf1\xe0\x00\x00", dst)
            # the floodlight command as the next sequence number
            sock.sendto(self._drw(len(self._setup), self._cmds[command]), dst)
            ok = self._drain(sock, dst, 2.0, want=0x4190)
            sock.sendto(b"\xf1\xe0\x00\x00", dst)
            self._drain(sock, dst, 0.5)
            if ok is None:
                _LOGGER.debug("no explicit 0x4190 ack (camera may still have applied it)")
        finally:
            sock.close()

    def test_connection(self) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self._timeout)
        try:
            self._discover_port(sock)
            return True
        finally:
            sock.close()
