import inspect
import typing

import h11

from .util import wrap_response


class Handler(object):
    def __init__(self, func: typing.Callable):
        if not callable(func):
            raise Exception('func must be a callable')
        self.func = func

    async def invoke(self, *args, **kwargs) -> (h11.Response, bytes):
        ret = self.func(*args, **kwargs)
        if inspect.isawaitable(ret):
            ret = await ret
        return wrap_response(ret)
