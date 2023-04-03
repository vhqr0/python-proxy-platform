import struct
import socket

from ..common import override
from ..stream import Stream
from .base import ProxyAcceptor


class TrojanAcceptor(ProxyAcceptor):
    pwd: bytes

    ensure_next_layer = True

    def __init__(self, pwd: bytes, **kwargs):
        super().__init__(**kwargs)
        assert len(pwd) == 56  # hex digest of sha224
        self.pwd = pwd

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()

        try:
            buf = await stream.read()
            if buf[59] == 3:  # domain
                alen = buf[60]
                buf, rest = buf[:65 + alen], buf[65 + alen:]
                pwd, crlf1, cmd, _, _, addr_bytes, port, crlf2 = \
                    struct.unpack(f'!56s2sBBB{alen}sH2s', buf)
                addr = addr_bytes.decode()
            elif buf[59] == 1:  # ipv4
                buf, rest = buf[:68], buf[68:]
                pwd, crlf1, cmd, _, addr_bytes, port = struct.unpack(
                    '!56s2sBB4sH2s', buf)
                addr = socket.inet_ntop(socket.AF_INET, addr_bytes)
            elif buf[59] == 4:  # ipv6
                buf, rest = buf[:80], buf[80:]
                pwd, crlf1, cmd, _, addr_bytes, port = struct.unpack(
                    '!56s2sBB16sH2s', buf)
                addr = socket.inet_ntop(socket.AF_INET6, addr_bytes)
            else:
                raise RuntimeError('invalid trojan header')
            if cmd != 1 or crlf1 != b'\r\n' or crlf2 != b'\r\n':
                raise RuntimeError('invalid trojan header')
            if pwd != self.pwd:
                raise RuntimeError('invalid trojan password')
            self.addr, self.rest = (addr, port), rest
            return stream
        except Exception as e:
            exc = e

        try:
            stream.close()
            await stream.wait_closed()
        except Exception:
            pass

        raise exc
