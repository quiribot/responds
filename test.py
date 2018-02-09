import logbook
import sys
import curio
from responds import Response
from responds.server import Server
from responds.router import Router

log = logbook.Logger('app')
logbook.StreamHandler(sys.stdout).push_application()

r = Router()
s = Server(r)


@r.route('/hello/async')
async def handle(event):
    log.info('our state: {}', event.wrapper.conn.our_state)
    log.info('their state: {}', event.wrapper.conn.their_state)
    log.info('app got body: {}', await event.body())
    log.info('our state: {}', event.wrapper.conn.our_state)
    log.info('their state: {}', event.wrapper.conn.their_state)
    return Response(status_code=200, headers=[], body=b'Hello world!')


kernel = curio.Kernel()
kernel.run(curio.tcp_server('0.0.0.0', 8080, s.tcp_handle))
