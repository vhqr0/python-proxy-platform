from ..acceptor import Acceptor, HTTPOrSocks5Acceptor
from ..common import override
from .base import Inbox, Request


class HTTPOrSocks5Inbox(Inbox):

    @override(Inbox)
    async def accept_primitive(self, next_acceptor: Acceptor) -> Request:
        acceptor = HTTPOrSocks5Acceptor(next_layer=next_acceptor)
        return await Request.from_acceptor(acceptor=acceptor)


class HTTPInbox(HTTPOrSocks5Inbox):
    scheme = 'http'


class Socks5Inbox(HTTPOrSocks5Inbox):
    scheme = 'socks5'
