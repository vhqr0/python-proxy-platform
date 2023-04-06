import asyncio
from typing import Any, Optional

from ..common import override
from ..stream import Stream, TCPStream
from .base import Connector


class TCPConnector(Connector):
    addr: tuple[str, int]
    tcp_extra_kwargs: dict[str, Any]

    def __init__(self,
                 addr: tuple[str, int],
                 tcp_extra_kwargs: Optional[dict[str, Any]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.addr = addr
        self.tcp_extra_kwargs = tcp_extra_kwargs \
            if tcp_extra_kwargs is not None else dict()

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        reader, writer = await asyncio.open_connection(
            self.addr[0],
            self.addr[1],
            **self.tcp_extra_kwargs,
        )
        stream = TCPStream(reader, writer)
        async with stream.cm(exc_only=True):
            if len(rest) != 0:
                await stream.writeall(rest)
            return stream
