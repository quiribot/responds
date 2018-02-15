import h11

# Stolen from Kyoukai
# modified to fit h11
# https://github.com/SunDwarf/Kyoukai/blob/master/kyoukai/util.py


def wrap_response(args) -> (h11.Response, bytes):
    """
    Wrap up a response, if applicable.
    This allows Flask-like `return "whatever"`.
    :param args: The arguments that are being wrapped.
    :param response_class: The Response class that is being used.
    """

    def get_body(arg):
        if type(arg) is bytes:
            return arg
        elif type(arg) is str:
            return arg.encode("utf-8")
        else:
            raise TypeError("view returned invalid body")

    if not args:
        # Return a 204 NO CONTENT.
        return h11.Response(status_code=204, headers=[]), b""

    if isinstance(args, tuple):
        # We enforce ``tuple`` here instead of any iterable.
        if len(args) == 1:
            # Only body, use 200 for the response code.
            return h11.Response(status_code=200, headers=[]), get_body(args[0])

        if len(args) == 2:
            # Body and status code.
            return h11.Response(
                status_code=args[1], headers=[]), get_body(args[0])

        if len(args) == 3:
            # Body, status code, and headers.
            return h11.Response(
                status_code=args[1], headers=args[2]), get_body(args[0])

        raise TypeError("Cannot return more than 3 arguments from a view")

    raise TypeError("view returned invalid arguments")


# https://stackoverflow.com/questions/3012421/python-memoising-deferred-lookup-property-decorator
def lazyprop(fn):
    attr_name = '_lazy_' + fn.__name__

    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazyprop
