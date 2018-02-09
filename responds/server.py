# server.py
# heavily inspired by h11's examples/curio-server.py
# modified to suit a flask-like api

from . import __version__, Response, Request
from enum import Enum
from itertools import count
from socket import SHUT_WR, SO_LINGER
from wsgiref.handlers import format_date_time
import curio
import h11
import logbook


class Environment(Enum):
    PROD = 1
    DEV = 2


class ServerException(Exception):
    def __init__(self, *args, **kwargs):
        super(*args, **kwargs)


class HTTPWrapper:
    log = logbook.Logger('responds-client')
    _next_id = count()

    def __init__(self, server, sock, addr):
        self.server = server
        self.sock = sock
        self.addr = addr
        self.conn = h11.Connection(h11.SERVER)
        self.ident = server.ident
        self.id = next(HTTPWrapper._next_id)

    async def send(self, event):
        if type(event) is h11.ConnectionClosed:
            # TODO
            raise ServerException('cannot send ConnectionClosed')
        data = self.conn.send(event)
        await self.sock.sendall(data)

    async def send_simple_response(self, status_code, body=None, headers=None):
        headers = self.server.create_headers() + (headers or [])
        if body:
            headers.append(('Content-Length', str(len(body))))
        else:
            headers.append(('Content-Length', '0'))
        res = h11.Response(status_code=status_code, headers=headers)
        await self.send_response(res, body)

    async def send_response(self, res, body=None):
        await self.send(res)
        if body:
            await self.send(h11.Data(data=body))
        await self.send(h11.EndOfMessage())

    async def maybe_send_error_response(self, exc):
        HTTPWrapper.log.debug('trying to send error response...')
        if self.conn.our_state not in {h11.IDLE, h11.SEND_RESPONSE}:
            HTTPWrapper.log.debug('...but we cant, because our state is: {}', self.conn.our_state)
            return
        try:
            if isinstance(exc, h11.RemoteProtocolError):
                status = exc.error_status_hint
            else:
                status = 500
            # TODO: custom handlers
            if self.server.env is Environment.DEV:
                body = str(exc).encode('utf-8')
            else:
                body = 'internal server error'
            await self.send_simple_response(status, body, [('Content-Type', 'text/plain')])
        except Exception as e:
            HTTPWrapper.log.error('error whilst trying to send error response: {}', e)

    async def _read(self):
        if self.conn.they_are_waiting_for_100_continue:
            go_ahead = h11.InformationalResponse(
                status_code=100,
                headers=self.server.create_headers())
            await self.send(go_ahead)
        try:
            data = await self.sock.recv(self.server.max_recv)
        except ConnectionError:
            data = b''
        self.conn.receive_data(data)

    async def next_event(self):
        while True:
            event = self.conn.next_event()
            if event is h11.NEED_DATA:
                await self._read()
                continue
            return event

    async def kill(self):
        with self.sock.blocking() as sock:
            try:
                sock.shutdown(SHUT_WR)
                sock.setsockopt(SO_LINGER, 0)
            except OSError:
                return
        # TODO: test this
        # we don't need to eat up data because we've set
        # SO_LINGER to 0 in the previous step
        # try:
        #     while True:
        #         if not await self.sock.recv(self.server.max_recv):
        #             break
        # finally:
        await self.sock.close()


class Server:
    def __init__(self, router, env=Environment.PROD, max_recv=65536, timeout=10, identity=None):
        if not identity:
            identity = 'responds/{} {}'.format(__version__, h11.PRODUCT_ID)
        self.router = router
        self.env = env
        self.max_recv = max_recv
        self.timeout = timeout
        self.ident = identity
        self.log = logbook.Logger('responds-server')

    def create_headers(self):
        return [
            ('Date', format_date_time(None).encode('ascii')),
            ('Server', self.ident)
        ]

    # TODO: 405 Method not allowed based on route.methods
    async def process_request(self, wrapper, event):
        route, params = self.router.match(event)
        if not route:
            return False
        req = Request(
            wrapper,
            event.method,
            params,
            event.target,
            event.headers,
            event.http_version)
        res = await route.call(req)
        if type(res) is not Response:
            raise Exception('expected handler return type to be Response')
        if wrapper.conn.their_state is h11.SEND_BODY:
            self.log.debug('handler didnt stream body')
            await req.body()
        async with curio.timeout_after(self.timeout):
            await res.send(wrapper)
        return True

    async def tcp_handle(self, sock, addr):
        wrapper = HTTPWrapper(self, sock, addr)
        while True:
            assert wrapper.conn.states == {
                h11.CLIENT: h11.IDLE, h11.SERVER: h11.IDLE}

            try:
                async with curio.timeout_after(self.timeout):
                    event = await wrapper.next_event()
                self.log.debug('server main loop got event: {}', event)
                # NOTE: we dont want to timeout the handler
                if type(event) is h11.Request:
                    if not await self.process_request(wrapper, event):
                        # TODO: 404 handler
                        await wrapper.send_simple_response(404, b'not found')
            except curio.TaskTimeout:
                # NOTE: Is it okay to ignore timeout on send
                async with curio.ignore_after(self.timeout):
                    # TODO: timeout handler
                    await wrapper.send_simple_response(408, None)
            except Exception as e:
                await wrapper.maybe_send_error_response(e)

            if wrapper.conn.our_state is h11.MUST_CLOSE:
                self.log.debug('must close connection: {}', wrapper.id)
                await wrapper.kill()
                return
            else:
                self.log.debug(
                    'our state is (supposedly) reusable: {}',
                    wrapper.conn.our_state)
                try:
                    wrapper.conn.start_next_cycle()
                except h11.ProtocolError as e:
                    self.log.warn(
                        'couldnt start next cycle: protocolerror: {}', e)
                    await wrapper.maybe_send_error_response(e)
                    # self.log.warn('ProtocolError for connection: {}', wrapper.id)
                    # self.log.warn(e)
                    # await wrapper.kill()
                    return
