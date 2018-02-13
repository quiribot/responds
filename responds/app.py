import curio
import h11
import logbook

from .wrapper import Request
from .context import HTTPContext
from .errors import (HTTPException, InternalServerError, MethodNotAllowed,
                     NotFound, RequestRedirect, RequestTimeout)
from .router import Router


class Application(object):
    def __init__(self,
                 name: str,
                 router: Router,
                 max_recv: int = 2**16,
                 timeout: int = 10):
        self.name = name
        self.router = router

        self.log = logbook.Logger(name)

    async def process_request(self, ctx: HTTPContext):
        req = ctx.request
        route, params = self.router.match(req)
        res, body = await route.invoke(ctx, params)
        await ctx.send_response(res, body)

    async def process_exception(self, ctx: HTTPContext, e: HTTPException):
        handler = self.router.handler_for(e)
        if handler:
            res, body = await handler.invoke(ctx, e)
        else:
            self.log.warn('no handler for {}', type(e))
            res = h11.Response(status_code=e.status_code, headers=[])
            body = type(e).__name__.encode('utf-8')
        await ctx.send_response(res, body)

    async def process_protocol_error(self, ctx: HTTPContext,
                                     e: h11.ProtocolError):
        handler = self.router.exception_handlers.get(type(e))
        if handler:
            res, body = await handler.invoke(ctx, e)
        else:
            self.log.warn('no handler for ProtocolError')
            res = h11.Response(
                status_code=e.error_status_hint, headers=[])  # TODO
            body = e.args[0].encode('utf-8')
        await ctx.send_response(res, body)

    async def on_client(self, sock, addr: (str, int)):
        self.log.info('got connection from {}:{}', *addr)
        ctx = HTTPContext(sock, addr)

        while True:
            assert ctx.conn.states == {
                h11.CLIENT: h11.IDLE,
                h11.SERVER: h11.IDLE
            }

            try:
                # TODO: custom timeouts
                async with curio.timeout_after(10):
                    self.log.debug('client loop waiting for event')
                    event = await ctx.next_event()
                    self.log.debug('client loop got event {}', event)
                if type(event) is h11.Request:
                    ctx.request = Request(ctx, event)
                    await self.process_request(ctx)
            except curio.TaskTimeout as e:
                http_e = RequestTimeout()
                http_e.__cause__ = e
                await self.process_exception(ctx, http_e)
            except (MethodNotAllowed, NotFound) as e:
                await self.process_exception(ctx, e)
            except RequestRedirect as e:
                # await self.process_exception(e)
                # TODO: 301: create a new path as the Location header
                pass
            except Exception as e:
                http_e = InternalServerError()
                http_e.__cause__ = e
                await self.process_exception(ctx, http_e)

            if ctx.conn.their_state is h11.SEND_BODY:
                # next_event til EndOfMessage
                async for part in ctx.request.stream():
                    pass

            if ctx.conn.our_state is h11.MUST_CLOSE:
                self.log.debug('not reusable, shutting down')
                await ctx.shutdown()
                return
            else:
                try:
                    self.log.debug('trying to re-use connection')
                    ctx.request = None
                    ctx.conn.start_next_cycle()
                except h11.ProtocolError as e:
                    self.log.error('unexpected state while trying '
                                   'to start next cycle: {}', ctx.conn.states)
                    await self.process_protocol_error(ctx, e)

    def run(self, host: str, port: int):
        kernel = curio.Kernel()
        kernel.run(curio.tcp_server(host, port, self.on_client))
