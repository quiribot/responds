from socket import SHUT_WR, SO_LINGER

import curio
import h11


class SessionBodyIterator(object):
    def __init__(self, session):
        self.session = session

    async def __aiter__(self):
        return self

    async def __anext__(self):
        event = await self.session.next_event()
        if type(event) is h11.EndOfMessage:
            raise StopAsyncIteration()
        return event.data


class Session(object):
    def __init__(self,
                 sock,
                 addr: (str, int),
                 max_recv: int = 2**16,
                 timeout: int = 10):
        self.sock = sock
        self.addr = addr
        self.max_recv = max_recv
        self.timeout = timeout

        self.conn = h11.Connection(h11.SERVER)

        self.environ = None
        self.request = None

    def stream(self):
        return SessionBodyIterator(self)

    async def send(self, event):
        assert type(event) is not h11.ConnectionClosed
        data = self.conn.send(event)
        # NOTE: Timeouts are handled by the application
        await self.sock.sendall(data)

    async def send_response(self, res: h11.Response, body: bytes = None):
        await self.send(res)
        if body:
            await self.send(h11.Data(data=body))
        await self.send(h11.EndOfMessage())

    async def _read_from_peer(self):
        if self.conn.they_are_waiting_for_100_continue:
            go_ahead = h11.InformationalResponse(
                status_code=100, headers=self.basic_headers())
            await self.send(go_ahead)
        try:
            # NOTE: Timeouts are handled by the application
            data = await self.sock.recv(self.max_recv)
        except ConnectionError:
            # They've stopped listening. Not much we can do about it here.
            data = b""
        self.conn.receive_data(data)

    async def next_event(self):
        while True:
            event = self.conn.next_event()
            if event is h11.NEED_DATA:
                await self._read_from_peer()
                continue
            return event

    async def shutdown(self):
        # Curio bug: doesn't expose shutdown()
        with self.sock.blocking() as real_sock:
            try:
                real_sock.shutdown(SHUT_WR)
            except OSError:
                # They're already gone, nothing to do
                return
        try:
            async with curio.timeout_after(self.timeout):
                while True:
                    got = await self.sock.recv(self.max_recv)
                    if not got:
                        break
        except curio.TaskTimeout:
            with self.sock.blocking() as real_sock:
                # force a reset when we call close in our finally block
                real_sock.setopt(SO_LINGER, 0)
        finally:
            await self.sock.close()
