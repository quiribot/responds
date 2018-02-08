import logbook
import sys
import curio
from h11 import Response
from responds.server import Server
from responds.router import Router

logbook.StreamHandler(sys.stdout).push_application()

r = Router()
s = Server(r)


@r.route('/hello/async')
async def handle(event, params):
    return Response(status_code=200, headers=[]), b'Hello world!'


kernel = curio.Kernel()
kernel.run(curio.tcp_server('0.0.0.0', 8080, s.tcp_handle))
