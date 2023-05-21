from abc import ABC, abstractmethod
from typing import Any, Optional

from proxy.defaults import OUTBOX_URL
from proxy.stream import ProxyRequest, Stream
from proxy.utils.loggable import Loggable
from proxy.utils.nameable import Nameable
from proxy.utils.override import override
from proxy.utils.pingable import Pingable
from proxy.utils.serializable import DispatchedSerializable
from proxy.utils.tabularable import Tabularable
from proxy.utils.url import URL
from proxy.utils.weightable import Weightable


class Outbox(Nameable, Pingable, Weightable, DispatchedSerializable['Outbox'],
             Tabularable, Loggable, ABC):
    url: URL
    fetcher: str
    tcp_extra_kwargs: dict[str, Any]

    fallback_url = URL.from_str(OUTBOX_URL)

    def __init__(self,
                 url: Optional[str] = None,
                 fetcher: str = '',
                 tcp_extra_kwargs: Optional[dict[str, Any]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        if url is None:
            url = self.scheme + '://'
        self.url = URL.from_str(url, fallback=self.fallback_url)
        self.fetcher = fetcher
        self.tcp_extra_kwargs = tcp_extra_kwargs \
            if tcp_extra_kwargs is not None else dict()

    def __str__(self) -> str:
        return f'<{self.name} {self.weight}>'

    @override(DispatchedSerializable)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['url'] = str(self.url)
        obj['fetcher'] = self.fetcher
        return obj

    @classmethod
    @override(DispatchedSerializable)
    def scheme_from_dict(cls, obj: dict[str, Any]) -> str:
        if 'scheme' in obj:
            return super().scheme_from_dict(obj)
        url = URL.from_str(obj.get('url') or '', fallback=cls.fallback_url)
        return url.scheme

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['url'] = obj.get('url') or ''
        kwargs['fetcher'] = obj.get('fetcher') or ''
        return kwargs

    @override(Tabularable)
    def summary(self) -> str:
        tabs = []
        tabs.append('{:>10}'.format(self.fetcher[:10]))
        tabs.append('{:>10}'.format(self.scheme[:5]))
        tabs.append('{:>10}'.format(str(self.delay)[:10]))
        tabs.append('{:>10}'.format(str(self.weight)[:10]))
        tabs.append(str(self))
        return ' | '.join(tabs)

    @abstractmethod
    async def connect(self, req: ProxyRequest) -> Stream:
        raise NotImplementedError
