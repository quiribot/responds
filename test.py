import logbook
import sys
from responds.app import Application
from responds.router import Router

log = logbook.Logger('test.py')
logbook.StreamHandler(sys.stdout).push_application()

r = Router()
s = Application('app', r)


class UserException(Exception):
    pass


@r.exception_handler(UserException)
async def handle_exception(*args):
    log.info('got args')
    log.info(args)
    return b'woops', 500, []


@r.route('/hello/raise')
async def handle_raise(event):
    raise UserException()


@r.route('/hello/async')
async def handle_hello(ctx, params):
    log.info('app got body: {}', await ctx.request.body())
    return b'hello world\n', 200, []


s.run('0.0.0.0', 8080)
