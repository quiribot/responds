import typing

from werkzeug.routing import Rule, Submount

from .handler import Handler
from .util import lazyprop


class Route(Handler):
    def __init__(self, func: typing.Callable):
        super().__init__(func)
        self.paths = []
        self.mapper = None

    @lazyprop
    def endpoint(self):
        return "_{}_{}".format(self.mapper.name, self.func.__name__)

    def add_path(self, route_url: str, methods: typing.Sequence[str],
                 strict_slashes: bool):
        self.paths.append((route_url, methods, strict_slashes))

    @property
    def submount(self):
        rules = []
        for route_url, methods, strict_slashes in self.paths:
            rules.append(
                Rule(
                    route_url,
                    methods=methods,
                    endpoint=self.endpoint,
                    strict_slashes=strict_slashes))
        return Submount("", rules)
