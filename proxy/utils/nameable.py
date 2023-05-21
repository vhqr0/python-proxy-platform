from typing import Any, Optional

from proxy.utils.loggable import Loggable
from proxy.utils.override import override
from proxy.utils.serializable import DispatchedSerializable


class Nameable(Loggable):
    name: str

    def __init__(self, name: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        if name is None:
            name = self.__class__.__name__
        self.name = name

    @override(DispatchedSerializable)
    def to_dict(self) -> dict[str, Any]:
        # Virtual inherit from DispatchedSerializable.
        obj = super().to_dict()  # type: ignore
        obj['name'] = self.name
        return obj

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        # Virtual inherit from DispatchedSerializable.
        kwargs = super().kwargs_from_dict(obj)  # type: ignore
        kwargs['name'] = obj.get('name') or cls.__name__
        return kwargs
