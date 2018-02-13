import h11

from .context import HTTPContext


class RequestBodyIterator(object):
    def __init__(self, ctx):
        self.ctx = ctx

    async def __aiter__(self):
        if self.ctx.conn.their_state is not h11.SEND_BODY:
            # User is not supposed to handle
            # this exception as it indicates
            # `async for request` is called
            # twice
            raise Exception('Cannot stream body twice')
        return self

    async def __anext__(self):
        event = await self.ctx.next_event()
        if type(event) is h11.EndOfMessage:
            raise StopAsyncIteration
        assert type(event) is h11.Data
        return event


class Request(object):
    # TODO: Docs
    """
    `h11.Request` wrapper
    """

    def __init__(self, ctx: HTTPContext, req: h11.Request):
        # FIXME: we have a mutually recursive reference here
        self.ctx = ctx
        self.method = req.method.decode('utf-8')
        self.path = req.target.decode('utf-8')
        self.headers = {
            key: value.encode('ascii') if type(value) is str else value
            for key, value in req.headers
        }
        self.http_version = req.http_version.decode('utf-8')

    def stream(self):
        return RequestBodyIterator(self.ctx)

    async def body(self):
        parts = bytearray()
        async for part in self.stream():
            parts += part
        return bytes(parts)


# TODO: Maybe use this to handle Content-Length
# class Response(object):
#     """
#     h11.Response wrapper
#     """
#     def __init__(self, status_code: int, headers: dict=None, body: bytes=None):
#         self.status_code = status_code
#         # HACK: headers should always be a dict
#         if type(headers) is dict:
#             self.headers = [(key, value) for key, value in headers]
#         else:
#             self.headers = headers
