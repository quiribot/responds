import h11

__version__ = '0.1'


# TODO: move
class RequestBodyIterator:
    def __init__(self, wrapper):
        self.wrapper = wrapper

    async def __aiter__(self):
        return self

    async def __anext__(self):
        event = await self.wrapper.next_event()
        if type(event) is h11.EndOfMessage:
            raise StopAsyncIteration
        assert type(event) is h11.Data
        return event


class Request:
    def __init__(self, wrapper, method, params, path, headers, http_version):
        self.wrapper = wrapper
        self.method = method
        self.params = params
        self.path = path
        self.headers = headers
        self.http_version = http_version

    def stream(self):
        if self.wrapper.conn.their_state is not h11.SEND_BODY:
            raise Exception('cannot call stream more than once')
        return RequestBodyIterator(self.wrapper)

    async def body(self):
        parts = bytearray()
        async for part in self.stream():
            parts += part
        return bytes(parts)


class Response:
    def __init__(self, status_code=200, headers=None, body=None):
        if not headers:
            headers = []
        if type(body) is str:
            body = body.encode('utf-8')
        if body:
            headers.append(('Content-Length', str(len(body))))
        self.status_code = status_code
        self.headers = headers
        self.body = body

    async def send(self, wrapper):
        headers = wrapper.server.create_headers() + self.headers
        await wrapper.send(h11.Response(
            status_code=self.status_code, headers=headers))
        if self.body:
            await wrapper.send(h11.Data(data=self.body))
        await wrapper.send(h11.EndOfMessage())
