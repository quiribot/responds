import logbook
import sys
from responds.app import Application
from responds.backends.httptools_ import HTTPToolsBackend

log = logbook.Logger("test.py")
logbook.StreamHandler(sys.stdout).push_application()

s = Application("app", HTTPToolsBackend, level=logbook.TRACE)


class UserException(Exception):
    pass


@s.error_handler(500)
async def handle_exception(*args):
    log.info("got args")
    log.info(args)
    return b"woops", 500, []


@s.route("/hello/raise")
async def handle_raise(request):
    raise UserException()


@s.route("/")
async def handle_hello(request):
    return "hello world\n"


s.build()
s.run('0.0.0.0', 8080)
