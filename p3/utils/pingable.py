import socket
from concurrent.futures import ThreadPoolExecutor
from timeit import timeit
from typing import Any, Optional

from typing_extensions import Self

from p3.utils.loggable import Loggable
from p3.utils.override import override
from p3.utils.serializable import DispatchedSerializable
from p3.utils.tabularable import Tabularable
from p3.utils.url import URL
from p3.utils.weightable import Weightable


class Delay:
    _delay: float

    def __init__(self, delay: float = -1.0):
        self._delay = delay

    @property
    def val(self) -> float:
        return self._delay

    def __str__(self) -> str:
        return '{:.2f}D'.format(self._delay)

    def __repr__(self) -> str:
        return 'Delay({})'.format(self._delay)

    def set(self, delay: float):
        self._delay = delay

    def reset(self):
        self._delay = -1.0


class Pingable(Weightable, Tabularable, Loggable):
    url: URL
    delay: Delay

    ping_skip: bool = False

    def __init__(self, delay: Optional[Delay] = None, **kwargs):
        super().__init__(**kwargs)
        if delay is None:
            delay = Delay()
        self.delay = delay

    @override(DispatchedSerializable)
    def to_dict(self) -> dict[str, Any]:
        # Virtual inherit from DispatchedSerializable.
        obj = super().to_dict()  # type: ignore
        obj['delay'] = self.delay.val
        return obj

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        # Virtual inherit from DispatchedSerializable.
        kwargs = super().kwargs_from_dict(obj)  # type: ignore
        delay = obj.get('delay')
        kwargs['delay'] = Delay(delay) if delay is not None else Delay()
        return kwargs

    def ping_connect(self):
        sock = socket.create_connection(self.url.addr, 2)
        sock.close()

    def ping(self, verbose: bool = False):

        if self.ping_skip:
            self.delay.set(0.0)
            self.weight.reset()
        else:
            try:
                delay = timeit(self.ping_connect, number=1)
                self.delay.set(delay)
                self.weight.reset()
            except Exception:
                self.delay.reset()
                self.weight.disable()

        if verbose:
            print(self.summary())

    @classmethod
    def ping_all(cls, objs: list[Self], verbose: bool = False):
        with ThreadPoolExecutor() as executor:
            executor.map(lambda peer: peer.ping(verbose=verbose), objs)