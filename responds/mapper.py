import typing

from werkzeug.exceptions import HTTPException
from werkzeug.routing import Map, Submount

from .handler import Handler
from .route import Route


class Mapper(object):
    def __init__(self, name: str, parent: 'Mapper' = None, prefix: str=""):
        self.name = name
        self.parent = parent
        self.prefix = prefix
        self.children = []
        self.routes = []
        self.route_map = None
        self.error_handlers = {}
        self._built = False

    @property
    def submount(self):
        rules = []
        for child in self.children:
            rules.append(child.submount)
        for route in self.routes:
            rules.append(route.submount)
        return Submount(self.prefix, rules)

    @property
    def all_routes(self):
        yield from iter(self.routes)

        for child in self.children:
            yield from child.all_routes

    def add_route(self, route: Route):
        route.mapper = self
        self.routes.append(route)

    def add_error_handler(self,
                          handler: Handler,
                          from_code: int,
                          to_code: int = None):
        if not to_code:
            codes = [from_code]
        else:
            codes = range(from_code, to_code)
        for code in codes:
            # TODO: check for overlapping handlers
            self.error_handlers[code] = handler

    def add_child(self, mapper: 'Mapper'):
        self.children.append(mapper)

    def build(self) -> Map:
        if self._built:
            raise Exception('already built')
        self._built = True
        self.route_map = Map([self.submount])
        return self.route_map

    def match(self, environ: dict) -> (Route, typing.Container[typing.Any]):
        adapter = self.route_map.bind_to_environ(environ)
        rule, params = adapter.match(return_rule=True)
        for route in self.all_routes:
            if route.endpoint == rule.endpoint:
                return route, params
        # it should never reach this path
        raise Exception('route not found?')

    def get_error_handler(self, e: HTTPException):
        try:
            return self.error_handlers[e.code]
        except KeyError:
            return None
