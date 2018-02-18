import abc
import typing
from socket import SHUT_WR, SO_LINGER

import curio
from werkzeug.datastructures import MultiDict
from werkzeug.wrappers import Response, Request


MAX_RECV = 2 ** 16


class Session(abc.ABC):
    def __init__(self, sock, addr: (str, int)):
        self.sock = sock
        self.remote_ip, self.remote_port = addr

    @abc.abstractmethod
    def create_environ(self) -> MultiDict:
        """
        Create a fake wsgi environment.
        Will be called by the backend,
        so it's possible to add extra
        arguments.
        """

    @abc.abstractmethod
    def create_response(self, response: Response,
                        environ: MultiDict) -> typing.Any:
        """
        Create a response usable by
        the backend.
        """

    async def shutdown(self):
        # Curio bug: doesn't expose shutdown()
        with self.sock.blocking() as real_sock:
            try:
                real_sock.shutdown(SHUT_WR)
            except OSError:
                # They're already gone, nothing to do
                return
        try:
            async with curio.timeout_after(10):  # TODO
                while True:
                    got = await self.sock.recv(MAX_RECV)  # TODO
                    if not got:
                        break
        except curio.TaskTimeout:
            with self.sock.blocking() as real_sock:
                # force a reset when we call close in our finally block
                real_sock.setopt(SO_LINGER, 0)
        except ConnectionResetError:  # dead
            return
        finally:
            await self.sock.close()


class Backend(abc.ABC):
    def __init__(self, app):
        self.app = app

    @abc.abstractmethod
    async def on_connection(self, sock, addr: (str, int)):
        """
        Called on every TCP connection.
        """


class Upgrade(abc.ABC):
    def __init__(self, app):
        self.app = app

    @abc.abstractmethod
    def create_response(self, req: Request) -> typing.Any:
        """
        Creates a response the original
        backend should return.
        Called when the Upgrade header
        matches this Upgrade class.
        """

    @abc.abstractmethod
    async def on_upgrade(self, req, sock, addr: (str, int)):
        """
        Intercepts control of the socket.
        Called when the Upgrade header
        matches this Upgrade class.
        """
