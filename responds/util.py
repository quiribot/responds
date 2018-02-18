from werkzeug.wrappers import Response

# Stolen from Kyoukai
# https://github.com/SunDwarf/Kyoukai/blob/master/kyoukai/util.py


def wrap_response(args) -> Response:
    """
    Wrap up a response, if applicable.
    This allows Flask-like `return "whatever"`.
    :param args: The arguments that are being wrapped.
    """

    if not args:
        # Return a 204 NO CONTENT.
        return Response("", status=204)

    if isinstance(args, tuple):
        # We enforce ``tuple`` here instead of any iterable.
        if len(args) == 1:
            # Only body, use 200 for the response code.
            return Response(args[0], status=200)

        if len(args) == 2:
            # Body and status code.
            return Response(args[0], status=args[1])

        if len(args) == 3:
            # Body, status code, and headers.
            return Response(args[0], status=args[1], headers=args[2])

        raise TypeError("Cannot return more than 3 arguments from a view")

    if isinstance(args, Response):
        return args

    return Response(args)


# https://stackoverflow.com/questions/3012421/python-memoising-deferred-lookup-property-decorator
def lazyprop(fn):
    attr_name = '_lazy_' + fn.__name__

    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazyprop
