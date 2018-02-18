from io import BytesIO

import curio
import httptools
import logbook
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import (BadRequest, InternalServerError,
                                 MethodNotAllowed, RequestTimeout)
from werkzeug.wrappers import Request, Response

from wsgiref.handlers import format_date_time
from . import Backend, Session
from ..app import Application
from ..fakewsgi import SaneWSGIWrapper, to_wsgi_environment


class HTTPToolsSession(Session):
    def __init__(self, sock, addr: (str, int)):
        super().__init__(sock, addr)

        self.parser = httptools.HttpRequestParser(self)

        # request props
        self.message_complete = False
        self.body = None
        self.url = b""
        self.headers = []

    def create_environ(self, fake: bool = False):
        # TODO: Content-Encoding: zlib
        ip, port = self.sock.getsockname()
        remote_addr = self.remote_ip + ":" + str(self.remote_port)
        if fake:
            # fake environ for a parser error handler
            return to_wsgi_environment(
                headers=self.headers,
                method=self.parser.get_method().decode("ascii"),
                path=self.url.decode("utf-8"),  # TODO: use httptools.parse_url
                body=self.body,
                server_name=ip,
                server_port=str(port),
                remote_addr=remote_addr)
        return to_wsgi_environment(
            headers=self.headers,
            method=self.parser.get_method().decode("ascii"),
            path=self.url.decode("utf-8"),
            body=self.body,
            server_name=ip,
            server_port=str(port),
            remote_addr=remote_addr)

    def create_response(self, response: Response, environ: MultiDict) -> bytes:
        wrapper = SaneWSGIWrapper()
        wrapper.unfuck_iterable(response(environ, wrapper.start_response))
        res = "HTTP/1.1 " + wrapper.status + "\r\n"
        for name, value in wrapper.headers:
            res += name + ": " + value + "\r\n"
        res += "\r\n"
        res = res.encode("utf-8")
        res += wrapper.real_body
        return res

    # httptools callbacks
    def on_message_begin(self):
        self.message_complete = False
        self.body = BytesIO()
        self.url = b""
        self.headers = []

    def on_url(self, url: bytes):
        self.url = url

    def on_header(self, name: bytes, value: bytes):
        self.headers.append((name.decode("ascii"), value.decode("ascii")))

    def on_headers_complete(self):
        pass

    def on_body(self, body: bytes):
        self.body.write(body)

    def on_message_complete(self):
        self.message_complete = True

    def on_chunk_header(self):
        pass

    def on_chunk_complete(self):
        pass


class HTTPToolsBackend(Backend):
    TIMEOUT = 10
    MAX_RECV = 2**16

    def __init__(self, app: Application, level: int = logbook.WARNING):
        super().__init__(app)

        self.log = logbook.Logger("httptools-backend", level=level)

    def add_common_headers(self, res: Response):
        res.headers["Server"] = b"responds-httptools"
        res.headers["X-Powered-By"] = b"responds"
        res.headers["Date"] = format(None).encode("ascii")

    async def handle_parser_error(self, session: HTTPToolsSession,
                                  e: httptools.HttpParserError):
        sock = session.sock
        if isinstance(e, httptools.HttpParserInvalidMethodError):
            http_e = MethodNotAllowed()
        elif isinstance(e, httptools.HttpParserError):
            http_e = BadRequest()
        elif isinstance(e, httptools.HttpParserUpgrade):
            http_e = BadRequest(description="Invalid upgrade header.")
        else:
            http_e = InternalServerError()
            http_e.__cause__ = e
        environ = session.create_environ(True)
        res = await self.app.handle_httpexception(environ, http_e)
        self.add_common_headers(res)
        await sock.sendall(session.create_response(res, environ))
        await session.shutdown()

    async def on_connection(self, sock, addr: (str, int)):
        session = HTTPToolsSession(sock, addr)
        while True:
            try:
                async with curio.timeout_after(HTTPToolsBackend.TIMEOUT):
                    self.log.debug("waiting for data")
                    data = await sock.recv(HTTPToolsBackend.MAX_RECV)
                    self.log.debug("got data")
                if not data:
                    self.log.debug("got empty buffer, assume close")
                    return
                session.parser.feed_data(data)
                if session.message_complete:
                    environ = session.create_environ()
                    res = await self.app.on_request(environ, Request(environ))
                    self.add_common_headers(res)
                    self.log.debug("got response: {}", res)
                    await sock.sendall(session.create_response(res, environ))
                if not session.parser.should_keep_alive():
                    await session.shutdown()
                    return
            except curio.TaskTimeout as e:
                # TODO: handle edge case where client doesnt close
                # on end
                http_e = RequestTimeout(description="timed out on read")
                http_e.__cause__ = e
                fake_env = session.create_environ(True)
                res = await self.app.handle_httpexception(fake_env, http_e)
                self.add_common_headers(res)
                data = session.create_response(res, fake_env)
                await sock.sendall(data)
                await session.shutdown()
                return
            except httptools.HttpParserError as e:
                return await self.handle_parser_error(session, e)
            except OSError:
                self.log.error("os error", exc_info=True)
                return
            except BrokenPipeError:
                self.log.error("io error: broken pipe", exc_info=True)
                return
            except Exception:
                # something really bad happened
                self.log.error(
                    "uncaught exception, file an issue",
                    exc_info=True)
                return
