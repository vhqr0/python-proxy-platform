import ssl
from abc import ABC
from typing import Any

from p3.common.tcp import TCPConnector
from p3.contrib.basic.ws import WSConnector
from p3.defaults import TLS_OUTBOX_HOST, WS_OUTBOX_HOST, WS_OUTBOX_PATH
from p3.iobox import Outbox
from p3.stream import Connector, Stream
from p3.utils.override import override


class V2rayNNetConnector(Connector):
    addr: tuple[str, int]
    net: str
    ws_path: str
    ws_host: str
    tls_host: str

    def __init__(self,
                 addr: tuple[str, int],
                 net: str = 'tcp',
                 ws_path: str = WS_OUTBOX_PATH,
                 ws_host: str = WS_OUTBOX_HOST,
                 tls_host: str = TLS_OUTBOX_HOST,
                 **kwargs):
        super().__init__(**kwargs)
        self.addr = addr
        self.net = net
        self.ws_path = ws_path
        self.ws_host = ws_host
        self.tls_host = tls_host

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        tcp_extra_kwargs: dict[str, Any] = dict()
        if self.net in ('tls', 'wss'):
            tls_ctx = ssl.create_default_context()
            tls_ctx.check_hostname = False
            tls_ctx.verify_mode = ssl.CERT_NONE
            tcp_extra_kwargs['ssl'] = tls_ctx
            tcp_extra_kwargs['server_hostname'] = self.tls_host
        connector: Connector
        connector = TCPConnector(
            tcp_extra_kwargs=tcp_extra_kwargs,
            addr=self.addr,
        )
        if self.net in ('ws', 'wss'):
            connector = WSConnector(
                path=self.ws_path,
                host=self.ws_host,
                next_layer=connector,
            )
        return await connector.connect(rest=rest)


class V2rayNNetCtxOutbox(Outbox, ABC):
    net: str
    ws_path: str
    ws_host: str
    tls_host: str

    def __init__(self,
                 net: str = 'tcp',
                 ws_path: str = WS_OUTBOX_PATH,
                 ws_host: str = WS_OUTBOX_HOST,
                 tls_host: str = TLS_OUTBOX_HOST,
                 **kwargs):
        super().__init__(**kwargs)
        self.net = net
        self.ws_path = ws_path
        self.ws_host = ws_host
        self.tls_host = tls_host

    def __str__(self) -> str:
        return '<{} {} {}>'.format(self.net, self.name, self.weight)

    @override(Outbox)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['net'] = self.net
        obj['ws_path'] = self.ws_path
        obj['ws_host'] = self.ws_host
        obj['tls_host'] = self.tls_host
        return obj

    @classmethod
    @override(Outbox)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['net'] = obj.get('net') or 'tcp'
        kwargs['ws_path'] = obj.get('ws_path') or WS_OUTBOX_PATH
        kwargs['ws_host'] = obj.get('ws_host') or WS_OUTBOX_HOST
        kwargs['tls_host'] = obj.get('tls_host') or TLS_OUTBOX_HOST
        return kwargs