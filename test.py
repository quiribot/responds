import json
import sys

import logbook

from responds.app import Application
from responds.backends.httptools_ import HTTPToolsBackend

log = logbook.Logger("test.py")
logbook.StreamHandler(sys.stdout).push_application()

s = Application("app", HTTPToolsBackend, level=logbook.TRACE)


class UserException(Exception):
    pass


@s.error_handler(500)
async def handle_exception(environ, e):
    return b"woops", 500, []


@s.route("/hello/raise")
async def handle_raise(ctx):
    raise UserException()


@s.route("/")
async def handle_hello(ctx):
    return "hello world\n"


@s.route("/dump/headers")
async def handle_dump_headers(ctx):
    headers = dict(ctx.request.headers)
    return json.dumps(headers)


@s.route("/dump/body", methods=("POST", ))
async def handle_dump_body(ctx):
    return ctx.request.get_data()


s.build()
s.run('0.0.0.0', 8080)
