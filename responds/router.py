import typing

from .wrapper import Request

from .policy import RoutingPolicy
from .handler import Handler
from .errors import HTTPException, NotFound
from .route import Params, Route
from .utils import compile_pattern


class Router(object):
    def __init__(self, routing_policy: RoutingPolicy = RoutingPolicy.LENIENT):
        self.policy = routing_policy

        self.routes = []
        self.error_handlers = {}
        self.exception_handlers = {}

    def _check_error_handler(self, code: int):
        if self.error_handlers.get(code):
            raise Exception(
                'there already is an error handler registered for {} code'.
                format(code))

    def add_route(self,
                  template: str,
                  func: typing.Callable,
                  methods: list = None,
                  routing_policy: RoutingPolicy = RoutingPolicy.LENIENT):
        if not methods:
            methods = ['GET']
        pattern, params = compile_pattern(template)
        route = Route(pattern, params, func, self, methods, routing_policy)
        self.routes.append(route)

    def route(self,
              template: str,
              methods: list = None,
              routing_policy: RoutingPolicy = RoutingPolicy.LENIENT):
        def wrapper(func):
            self.add_route(template, func, methods, routing_policy)
            return func

        return wrapper

    def add_error_handler(self,
                          func: typing.Callable,
                          from_code: int,
                          to_code: int = None):
        if not to_code:
            self._check_error_handler(from_code)
            self.error_handlers[from_code] = Handler(func)
        else:
            for i in range(from_code, to_code):
                self._check_error_handler(i)
                self.error_handlers[i] = Handler(func)

    def error_handler(self, from_code: int,
                      to_code: int = None) -> typing.Callable:
        def wrapper(func):
            self.add_error_handler(func, from_code, to_code)
            return func

        return wrapper

    def add_exception_handler(self, func: typing.Callable, exc: Exception):
        if self.exception_handlers.get(exc):
            raise Exception('there already is an exception '
                            'handler registered for {} exception'.format(exc))
        self.exception_handlers[exc] = Handler(func)

    def exception_handler(self, exc: Exception) -> typing.Callable:
        def wrapper(func):
            self.add_exception_handler(func, exc)
            return func

        return wrapper

    def match(self, req: Request) -> (Route, Params):
        for route in self.routes:
            params = route.match(req.path, req.method)
            if params:
                return route, params

        raise NotFound()

    def handler_for(self, exc: Exception):
        if isinstance(exc, HTTPException):
            return self.error_handlers.get(exc.status_code)
        return self.exception_handlers.get(type(exc))
