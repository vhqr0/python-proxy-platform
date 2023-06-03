"""Socks5 protocol implementation.

See RFC 1928 for more detials.

Links:
  https://www.rfc-editor.org/rfc/rfc1928
"""
import socket
from collections.abc import Sequence
from dataclasses import dataclass
from struct import Struct
from typing import Union

from typing_extensions import Self

from p3.common.tcp import TCPConnector
from p3.iobox import Outbox, TLSCtxOutbox
from p3.stream import ProxyAcceptor, ProxyConnector, ProxyRequest, Stream
from p3.stream.enums import BaseEnumMixin, BEnum
from p3.stream.errors import ProtocolError
from p3.stream.structs import HStruct
from p3.utils.override import override

BBStruct = Struct('!BB')
BBBStruct = Struct('!BBB')


class Socks5EnumMixin(BaseEnumMixin):
    scheme = 'socks5'


class Socks5BEnum(Socks5EnumMixin, BEnum):
    pass


class Socks5Ver(Socks5BEnum):
    V4 = 4
    V5 = 5


class Socks5Rsv(Socks5BEnum):
    Zero = 0


class Socks5AuthMethod(Socks5BEnum):
    """
    o  X'00' NO AUTHENTICATION REQUIRED
    o  X'01' GSSAPI
    o  X'02' USERNAME/PASSWORD
    o  X'03' to X'7F' IANA ASSIGNED
    o  X'80' to X'FE' RESERVED FOR PRIVATE METHODS
    o  X'FF' NO ACCEPTABLE METHODS
    """
    NoAuthenticationRequired = 0
    GSSAPI = 1
    UsernamePassword = 2
    NoAcceptableMethods = 0xff


class Socks5Cmd(Socks5BEnum):
    """
    o  CONNECT X'01'
    o  BIND X'02'
    o  UDP ASSOCIATE X'03'
    """
    Connect = 1
    Bind = 2
    UDPAssociate = 3


class Socks5Atyp(Socks5BEnum):
    """
    o  IP V4 address: X'01'
    o  DOMAINNAME: X'03'
    o  IP V6 address: X'04'
    """
    IPV4 = 1
    IPV6 = 4
    DOMAINNAME = 3


class Socks5Rep(Socks5BEnum):
    """
    o  X'00' succeeded
    o  X'01' general SOCKS server failure
    o  X'02' connection not allowed by ruleset
    o  X'03' Network unreachable
    o  X'04' Host unreachable
    o  X'05' Connection refused
    o  X'06' TTL expired
    o  X'07' Command not supported
    o  X'08' Address type not supported
    o  X'09' to X'FF' unassigned
    """
    Succeeded = 0
    GeneralSocksServerFailure = 1
    ConnectionNotAllowedByRuleset = 2
    NetworkUnreachable = 3
    HostUnreachable = 4
    ConnectionRefused = 5
    TTLExpired = 6
    CommandNotSupported = 7
    AddressTypeNotSupported = 8


@dataclass
class Socks5Addr:
    atyp: Socks5Atyp
    addr: tuple[str, int]

    IPv4Struct = Struct('!B4sH')
    IPv6Struct = Struct('!B16sH')

    def __bytes__(self) -> bytes:
        addr, port = self.addr
        if self.atyp is Socks5Atyp.DOMAINNAME:
            addr_bytes = addr.encode()
            alen = len(addr_bytes)
            return BBStruct.pack(self.atyp, alen) + \
                addr_bytes + \
                HStruct.pack(port)
        elif self.atyp is Socks5Atyp.IPV4:
            addr_bytes = socket.inet_pton(socket.AF_INET, addr)
            return self.IPv4Struct.pack(self.atyp, addr_bytes, port)
        elif self.atyp is Socks5Atyp.IPV6:
            addr_bytes = socket.inet_pton(socket.AF_INET6, addr)
            return self.IPv6Struct.pack(self.atyp, addr_bytes, port)
        else:
            self.atyp.raise_from_scheme()

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        _atyp = await stream.readB()
        atyp = Socks5Atyp(_atyp)
        if atyp is Socks5Atyp.DOMAINNAME:
            alen = await stream.readB()
            addr_bytes = await stream.readexactly(alen)
            port = await stream.readH()
            addr = addr_bytes.decode()
        elif atyp is Socks5Atyp.IPV4:
            addr_bytes, port = await stream.read_struct(cls.IPv4Struct)
            addr = socket.inet_ntop(socket.AF_INET, addr_bytes)
        elif atyp is Socks5Atyp.IPV6:
            addr_bytes, port = await stream.read_struct(cls.IPv6Struct)
            addr = socket.inet_ntop(socket.AF_INET6, addr_bytes)
        else:
            atyp.raise_from_scheme()
        return cls(atyp, (addr, port))


@dataclass
class Socks5AuthRequest:
    """
    +----+----------+----------+
    |VER | NMETHODS | METHODS  |
    +----+----------+----------+
    | 1  |    1     | 1 to 255 |
    +----+----------+----------+
    """
    methods: Union[bytes, Sequence[Socks5AuthMethod]]

    def __bytes__(self) -> bytes:
        nmethods = len(self.methods)
        methods = bytes(self.methods)
        return BBStruct.pack(Socks5Ver.V5, nmethods) + methods

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        ver, nmethods = await stream.read_struct(BBStruct)
        Socks5Ver.V5.ensure(ver)
        if nmethods == 0:
            raise ProtocolError('socks5', 'auth', 'methods')
        methods = await stream.readexactly(nmethods)
        return cls(methods)


@dataclass
class Socks5AuthReply:
    """
    +----+--------+
    |VER | METHOD |
    +----+--------+
    | 1  |   1    |
    +----+--------+
    """
    method: Socks5AuthMethod

    def __bytes__(self) -> bytes:
        return BBStruct.pack(Socks5Ver.V5, self.method)

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        ver, _method = await stream.read_struct(BBStruct)
        Socks5Ver.V5.ensure(ver)
        method = Socks5AuthMethod(_method)
        return cls(method)


@dataclass
class Socks5Request:
    """
    +----+-----+-------+------+----------+----------+
    |VER | CMD |  RSV  | ATYP | DST.ADDR | DST.PORT |
    +----+-----+-------+------+----------+----------+
    | 1  |  1  | X'00' |  1   | Variable |    2     |
    +----+-----+-------+------+----------+----------+
    """
    cmd: Socks5Cmd
    dst: Socks5Addr

    def __bytes__(self) -> bytes:
        return BBBStruct.pack(Socks5Ver.V5, self.cmd, 0) + bytes(self.dst)

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        ver, _cmd, rsv = await stream.read_struct(BBBStruct)
        Socks5Ver.V5.ensure(ver)
        Socks5Rsv.Zero.ensure(rsv)
        cmd = Socks5Cmd(_cmd)
        dst = await Socks5Addr.read_from_stream(stream)
        return cls(cmd, dst)


@dataclass
class Socks5Reply:
    """
    +----+-----+-------+------+----------+----------+
    |VER | REP |  RSV  | ATYP | BND.ADDR | BND.PORT |
    +----+-----+-------+------+----------+----------+
    | 1  |  1  | X'00' |  1   | Variable |    2     |
    +----+-----+-------+------+----------+----------+
    """
    rep: Socks5Rep
    bnd: Socks5Addr

    def __bytes__(self) -> bytes:
        return BBBStruct.pack(Socks5Ver.V5, self.rep, 0) + bytes(self.bnd)

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        ver, _rep, rsv = await stream.read_struct(BBBStruct)
        Socks5Ver.V5.ensure(ver)
        Socks5Rsv.Zero.ensure(rsv)
        rep = Socks5Rep(_rep)
        bnd = await Socks5Addr.read_from_stream(stream)
        return cls(rep, bnd)


class Socks5Connector(ProxyConnector):
    AUTH_REQ = bytes(
        Socks5AuthRequest((Socks5AuthMethod.NoAuthenticationRequired, )))

    ensure_next_layer = True

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.connect(self.AUTH_REQ)
        async with stream.cm(exc_only=True):
            arep = await Socks5AuthReply.read_from_stream(stream)
            Socks5AuthMethod.NoAuthenticationRequired.ensure(arep.method)
            dst = Socks5Addr(Socks5Atyp.DOMAINNAME, self.addr)
            req = bytes(Socks5Request(Socks5Cmd.Connect, dst))
            if len(rest) != 0:
                req += rest
            await stream.writedrain(req)
            rep = await Socks5Reply.read_from_stream(stream)
            Socks5Rep.Succeeded.ensure(rep.rep)
            return stream


class Socks5Acceptor(ProxyAcceptor):
    AUTH_REP = bytes(Socks5AuthReply(
        Socks5AuthMethod.NoAuthenticationRequired))
    REP = bytes(
        Socks5Reply(
            Socks5Rep.Succeeded,
            Socks5Addr(Socks5Atyp.IPV4, ('0.0.0.0', 0)),
        ))

    ensure_next_layer = True

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()
        async with stream.cm(exc_only=True):
            await self.dispatch_socks5(stream)
            return stream

    async def dispatch_socks5(self, stream: Stream):
        areq = await Socks5AuthRequest.read_from_stream(stream)
        if Socks5AuthMethod.NoAuthenticationRequired not in areq.methods:
            raise ProtocolError('socks5', 'auth', 'methods')
        await stream.writedrain(self.AUTH_REP)
        req = await Socks5Request.read_from_stream(stream)
        Socks5Cmd.Connect.ensure(req.cmd)
        self.addr = req.dst.addr
        await stream.writedrain(self.REP)


class Socks5Outbox(Outbox):
    scheme = 'socks5'

    @override(Outbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        connector = Socks5Connector(addr=req.addr, next_layer=next_connector)
        return await connector.connect(rest=req.rest)


class Socks5SOutbox(Socks5Outbox, TLSCtxOutbox):
    scheme = 'socks5s'
