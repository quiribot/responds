import inspect
import typing

import h11


class Handler(object):
    def __init__(self, func: typing.Callable):
        if not callable(func):
            raise Exception('func must be a callable')
        self.func = func

    async def invoke(self, *args, **kwargs) -> (h11.Response, bytes):
        ret = self.func(*args, **kwargs)
        if inspect.isawaitable(ret):
            ret = await ret
        try:
            body, status_code, headers = ret
            return h11.Response(status_code=status_code, headers=headers), body
        except ValueError as e:
            raise Exception('handlers must return a tuple of three') from e
