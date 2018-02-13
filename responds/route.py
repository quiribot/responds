import typing

from .handler import Handler
from .errors import MethodNotAllowed, RequestRedirect
from .policy import RoutingPolicy

# from .wrapper import Request


class Params:
    def __init__(self, params, groups):
        # TODO: Edge case where len(groups) > len(params) or otherwise
        self._params = dict(zip(params, groups))

    def __getattr__(self, attr):
        try:
            return self._params[attr]
        except KeyError as e:
            raise AttributeError() from e


class Route(Handler):
    """
    Holds the route handler, allowed methods
    and the like.
    """

    def __init__(
            self,
            pattern: typing.Pattern,
            params: list,
            func: typing.Callable,
            parent,  # .router.Router
            methods: list,
            routing_policy=None):
        super().__init__(func)
        self.pattern = pattern
        self.params = params
        self.parent = parent
        self.methods = methods
        self.policy = routing_policy or parent.policy

    def match(self, target: str, method: str):
        if method not in self.methods:
            raise MethodNotAllowed()
        matches = self.pattern.match(target)
        if not matches:
            return None
        if self.policy is RoutingPolicy.STRICT and not target.endswith('/'):
            raise RequestRedirect()
        return Params(self.params, matches.groups())
