import inspect
import typing

from .mapper import Mapper
from .route import Route


def route(route_rule: str,
          methods: typing.Sequence[str] = ("GET", ),
          strict_slashes: bool = False):
    def __inner(func):
        if not hasattr(func, "_route"):
            setattr(func, "_route", Route(func))
        func._route.add_path(route_rule, methods, strict_slashes)
        return func

    return __inner


def error_handler(from_code: int, to_code: int = None):
    def __inner(func):
        setattr(func, "_from_to", (from_code, to_code))
        return func

    return __inner


def prefix(prefix: str = ""):
    def __inner(cls):
        setattr(cls, "_prefix", prefix)
        return cls

    return __inner


class Group(object):
    def inherit_from(self, parent: Mapper) -> Mapper:
        prefix = getattr(self.__class__, "_prefix", "")
        mapper = Mapper(self.__class__.__name__, parent, prefix)
        methods = inspect.getmembers(self, predicate=inspect.ismethod)
        for _, method in methods:
            if hasattr(method, "_route"):
                method._route.func = method._route.func.__get__(
                    self, self.__class__)
                mapper.add_route(method._route)
            elif hasattr(method, "_from_to"):
                (from_code, to_code) = method._from_to
                mapper.add_error_handler(method, from_code, to_code)
        return mapper
