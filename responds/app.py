import typing
from collections import namedtuple

import curio
import logbook
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import (BadRequestKeyError, HTTPException,
                                 InternalServerError, MethodNotAllowed)
from werkzeug.routing import NotFound, RequestRedirect
from werkzeug.wrappers import Request, Response

from .backends import Backend
from .handler import Handler
from .mapper import Mapper
from .route import Route

Context = namedtuple("Context", ("request", "params", "environ"))


class Application(object):
    def __init__(self,
                 name: str,
                 backend: Backend,
                 level: int = logbook.WARNING):
        self.log = logbook.Logger(name, level=level)
        self.backend = backend(self, level)
        self.mapper = Mapper(name)
        self.listening_to = (None, None)

    async def handle_httpexception(self, environ: MultiDict,
                                   e: HTTPException) -> Response:
        handler = self.mapper.get_error_handler(e)
        if not handler:
            self.log.warn("no handler for {}", type(e))
            return e.get_response(environ)
        # FIXME: if the handler raises, it rolls up to the backend
        return await handler.invoke(environ, e)

    # TODO: we'll need to add Server, X-Powered-By and Date headers
    async def on_request(self, environ: MultiDict, req: Request) -> Response:
        request = Request(environ)

        try:
            route, params = self.mapper.match(environ)
        except NotFound as e:
            self.log.debug("couldnt match for {}", req.path)
            return await self.handle_httpexception(environ, e)
        except MethodNotAllowed as e:
            self.log.debug("no valid method for {req.method} {req.path}",
                           request)
            return await self.handle_httpexception(environ, e)
        except RequestRedirect as e:
            self.log.debug("redirecting (missing slash)")
            return e.get_response(environ)

        try:
            # TODO: OPTIONS method
            return await route.invoke(
                Context(request=req, params=params, environ=environ))
        except BadRequestKeyError as e:
            self.log.debug("BadRequestKeyError?")
            return await self.handle_httpexception(environ, e)
        except HTTPException as e:
            return await self.handle_httpexception(environ, e)
        except Exception as e:
            self.log.debug(
                "handler raised exception, wrapping in InternalServerError",
                exc_info=True)
            http_e = InternalServerError()
            http_e.__cause__ = e
            return await self.handle_httpexception(environ, http_e)

    def route(self,
              route_url: str,
              methods: typing.Sequence[str] = ("GET", ),
              strict_slashes: bool = False):
        def __inner(func):
            if not hasattr(func, "_route"):
                route = Route(func)
                setattr(func, "_route", route)
                self.mapper.add_route(route)
            func._route.add_path(route_url, methods, strict_slashes)
            return func

        return __inner

    def error_handler(self, from_code: int, to_code: int = None):
        def __inner(func):
            handler = Handler(func)
            self.mapper.add_error_handler(handler, from_code, to_code)
            return func

        return __inner

    def build(self, *args, **kwargs):
        return self.mapper.build(*args, **kwargs)

    def run(self, host: str, port: int):
        self.listening_to = (host, port)
        if not self.mapper._built:
            raise Exception("you need to call application.build() first")
        curio.run(curio.tcp_server(host, port, self.backend.on_connection))
