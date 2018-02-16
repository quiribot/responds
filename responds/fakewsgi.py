# Pretty much stolen from Kyoukai
# https://github.com/SunDwarf/Kyoukai/blob/master/kyoukai/wsgi.py
import sys
import typing
from io import BytesIO
from urllib.parse import urlsplit

import h11
from werkzeug.datastructures import MultiDict
from werkzeug.wrappers import Response


class SaneWSGIWrapper(object):
    """
    Forces a WSGI object to be in-line.
    """

    def __init__(self):
        self.headers = []
        self.real_body = b""

        self.status = None
        self.reason = None

    def start_response(self,
                       status,
                       headers: typing.List[tuple],
                       exc_info=None):
        """
        Used as the ``start_response`` callable when interacting with WSGI devices.
        """
        status = status.split()
        self.status = int(status[0])
        self.reason = ' '.join(status[1:])
        self.headers = headers

    def unfuck_iterable(self, i: typing.Iterable):
        """
        Unfucks the WSGI iterable into a single body.
        """
        for part in i:
            self.real_body += part

    def __str__(self):
        """
        Converts this into the string format.
        """
        return self.format()


def to_wsgi_environment(headers: list,
                        method: str,
                        path: str,
                        body: BytesIO = None,
                        server_name: str = 'responds',
                        server_port: str = '8080',
                        remote_addr: str = '127.0.0.1:2000') -> MultiDict:
    if isinstance(headers, dict):
        headers = headers.items()

    # urlsplit the path
    sp_path = urlsplit(path)

    if body is None:
        body = BytesIO()

    environ = MultiDict({
        # Basic items
        "PATH_INFO": sp_path.path,
        "QUERY_STRING": sp_path.query,
        "SERVER_PROTOCOL": "HTTP/1.1",
        "REQUEST_METHOD": method,
        "SERVER_NAME": server_name,
        "SERVER_PORT": server_port,
        "REMOTE_ADDR": remote_addr,
        # WSGI protocol things
        "wsgi.errors": sys.stderr,
        "wsgi.url_scheme": "http",
        "wsgi.input": body,
        "wsgi.input_terminated": True,
        "wsgi.async": True,
        "wsgi.multithread": True,  # technically false sometimes, but oh well
        "wsgi.multiprocess": False,
        "wsgi.run_once": False
    })
    environ["wsgi.version"] = (1, 0)

    for header, value in headers:
        name = (header if type(header) is str else header.decode('ascii')).upper().replace("-", "_")
        if header not in ("Content-Type", "Content-Length"):
            name = "HTTP_{}".format(name)

        environ.add(name, value
                    if type(value) is str else value.decode('ascii'))

    return environ


def unfuck_wsgi_response(response: Response,
                         environ: dict) -> (h11.Response, bytes):
    wrapper = SaneWSGIWrapper()
    iterator = response(environ, wrapper.start_response)
    wrapper.unfuck_iterable(iterator)
    return h11.Response(
        status_code=wrapper.status,
        reason=wrapper.reason,
        headers=wrapper.headers), wrapper.real_body
