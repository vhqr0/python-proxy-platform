from abc import ABC, abstractmethod
from typing import Any

from proxy.iobox.outbox import Outbox
from proxy.utils.loggable import Loggable
from proxy.utils.nameable import Nameable
from proxy.utils.override import override
from proxy.utils.serializable import DispatchedSerializable


class Fetcher(Nameable, DispatchedSerializable['Fetcher'], Loggable, ABC):
    url: str

    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url

    def __str__(self) -> str:
        return '<{}://{}>'.format(self.scheme, self.name)

    @override(DispatchedSerializable)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['url'] = self.url
        return obj

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['url'] = obj['url']
        return kwargs

    @abstractmethod
    def fetch(self) -> list[Outbox]:
        raise NotImplementedError
