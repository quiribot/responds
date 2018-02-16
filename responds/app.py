import typing

import curio
import h11
import logbook
from werkzeug.exceptions import (BadRequestKeyError, HTTPException,
                                 InternalServerError, MethodNotAllowed,
                                 RequestTimeout)
from werkzeug.wrappers import Request
from werkzeug.routing import RequestRedirect, NotFound

from .fakewsgi import to_wsgi_environment, unfuck_wsgi_response
from .handler import Handler
from .mapper import Mapper
from .route import Route
from .session import Session

ADDRESS = '{}:{}'


class Application(object):
    def __init__(self, name: str, level: int = logbook.WARNING):
        self.log = logbook.Logger(name, level=level)
        self.mapper = Mapper(name)
        self.listening_to = (None, None)

    def create_environ(self, session: Session,
                       req: h11.Request = None) -> dict:
        # if the request is None, it's a fake environment
        # for an error handler
        if req is None:
            return to_wsgi_environment(
                headers=[],
                method='',
                path='/',
                server_name=self.listening_to[0],
                server_port=str(self.listening_to[1]),
                remote_addr=ADDRESS.format(*session.addr))
        # TODO: I'm unsure if passing in the body
        # is really necessary
        return to_wsgi_environment(
            headers=req.headers,
            method=req.method.decode('ascii'),
            path=req.target.decode('utf-8'),
            server_name=self.listening_to[0],
            server_port=str(self.listening_to[1]),
            remote_addr=ADDRESS.format(*session.addr))

    async def handle_httpexception(self, session: Session,
                                   e: HTTPException) -> (h11.Response, bytes):
        handler = self.mapper.get_error_handler(e)
        if not handler:
            self.log.warn('no handler for {}', type(e))
            return unfuck_wsgi_response(
                e.get_response(session.environ), session.environ)
        return await handler.invoke(session, e)

    # TODO: we'll need to add Server, X-Powered-By and Date headers
    async def on_request(self, session: Session,
                         req: h11.Response) -> (h11.Response, bytes):
        session.environ = self.create_environ(session, req)
        session.request = Request(session.environ)

        try:
            route, params = self.mapper.match(session.environ)
        except NotFound as e:
            self.log.debug('couldnt match for {}', req.target)
            return await self.handle_httpexception(session, e)
        except MethodNotAllowed as e:
            self.log.debug('no valid method for {req.method} {req.path}',
                           session.request)
            return await self.handle_httpexception(session, e)
        except RequestRedirect as e:
            self.log.debug('redirecting (missing slash)')
            return unfuck_wsgi_response(
                e.get_response(session.environ), session.environ)

        try:
            # TODO: OPTIONS method
            return await route.invoke(session, session.request)
        except BadRequestKeyError as e:
            self.log.debug('BadRequestKeyError?')
            return await self.handle_httpexception(session, e)
        except HTTPException as e:
            return await self.handle_httpexception(session, e)
        except Exception as e:
            self.log.debug(
                'handler raised exception, wrapping in InternalServerError',
                exc_info=True)
            http_e = InternalServerError()
            http_e.__cause__ = e
            return await self.handle_httpexception(session, http_e)

    async def on_connection(self, sock, addr: (str, int)):
        self.log.info('got connection from {}:{}', *addr)
        session = Session(sock, addr)

        res, body = None, None

        while True:
            assert session.conn.states == {
                h11.CLIENT: h11.IDLE,
                h11.SERVER: h11.IDLE
            }

            try:
                # TODO: timeout
                async with curio.timeout_after(10):
                    self.log.debug('client loop waiting for event')
                    event = await session.next_event()
                    self.log.debug('client loop got event {}', event)
                if type(event) is h11.Request:
                    # TODO: we'll need to somehow pass
                    # Data events to on_request
                    res, body = await self.on_request(session, event)
            except curio.TaskTimeout as e:
                http_e = RequestTimeout(description='timed out on read')
                http_e.__cause__ = e
                session.environ = self.create_environ(session)
                res, body = await self.handle_httpexception(session, http_e)
            except Exception:
                # something bad happened
                # because we catch handler exceptions
                # in on_request
                self.log.error('uncaught exception while processing the request', exc_info=True)

            # FIXME: refactor NO GOOOOOOOOOOD
            if res:
                try:
                    await session.send_response(res, body)
                    res, body = None, None
                except BrokenPipeError:
                    # aaaaaaaa
                    self.log.error('io error: broken pipe')
                    await session.shutdown()
                    return

            if session.conn.their_state is h11.SEND_BODY:
                # next_event til EndOfMessage
                async for part in session.stream():
                    pass

            if session.conn.our_state is h11.MUST_CLOSE:
                self.log.debug('not reusable, shutting down')
                await session.shutdown()
                return
            else:
                try:
                    self.log.debug('trying to re-use connection')
                    session.environ = None
                    session.request = None
                    session.conn.start_next_cycle()
                except h11.ProtocolError as e:
                    self.log.error('unexpected state while trying '
                                   'to start next cycle: {}',
                                   session.conn.states)
                    # TODO: await self.process_protocol_error(ctx, e)

    def route(self,
              route_url: str,
              methods: typing.Sequence[str] = ('GET',),
              strict_slashes: bool = False):
        def __inner(func):
            if not hasattr(func, '_route'):
                route = Route(func)
                setattr(func, '_route', route)
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
            raise Exception('you need to call application.build() first')
        curio.run(curio.tcp_server(host, port, self.on_connection))
