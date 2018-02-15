import logbook
import sys
from responds.app import Application

log = logbook.Logger('test.py')
logbook.StreamHandler(sys.stdout).push_application()

s = Application('app')


class UserException(Exception):
    pass


@s.error_handler(500)
async def handle_exception(*args):
    log.info('got args')
    log.info(args)
    return b'woops', 500, []


@s.route('/hello/raise')
async def handle_raise(session, params):
    raise UserException()


@s.route('/hello/async')
async def handle_hello(session, params):
    log.info('handle_hello')
    return b'hello world\n', 200, []


s.build()
s.run('0.0.0.0', 8080)
