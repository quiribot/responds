class HTTPException(Exception):
    pass


class RequestRedirect(HTTPException):
    """
    Raised when the route needs a trailing slash,
    while the request doesn't end with one one.

    Also look at `RoutingPolicy.STRICT`.
    """
    status_code = 301


class NotFound(HTTPException):
    """
    Raised when none of the routes match the request.
    """
    status_code = 404


class MethodNotAllowed(HTTPException):
    """
    Raised when the request doesn't match methods
    allowed.
    """
    status_code = 405


class RequestTimeout(HTTPException):
    """
    Raised when the client loop hits a
    curio.TaskTimeout exception (__cause__).
    """
    status_code = 408


class InternalServerError(HTTPException):
    """
    Raised when a handler (or anything else)
    raises an exception. Parent exception is
    stored in the __cause__ attribute.
    """
    status_code = 500
