from dataclasses import dataclass

from typing_extensions import Self

from p3.stream.acceptor import Acceptor
from p3.stream.connector import Connector
from p3.stream.stream import Stream


class ProxyConnector(Connector):
    addr: tuple[str, int]

    def __init__(self, addr: tuple[str, int], **kwargs):
        super().__init__(**kwargs)
        self.addr = addr


class ProxyAcceptor(Acceptor):
    addr: tuple[str, int]


@dataclass
class ProxyRequest:
    addr: tuple[str, int]
    rest: bytes

    def __str__(self):
        return '<{} {} {}B>'.format(self.addr[0], self.addr[1], len(self.rest))

    @classmethod
    async def from_acceptor(
        cls,
        acceptor: ProxyAcceptor,
    ) -> tuple[Stream, Self]:
        stream = await acceptor.accept()
        addr = acceptor.addr
        rest = stream.pop()
        return stream, cls(addr=addr, rest=rest)
