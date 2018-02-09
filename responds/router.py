import re
from .route import Route
from urllib.parse import urlparse


PARAM_TEMPLATE_PATTERN = re.compile(r'<(.+[^\\])>')


# TODO: Multi wildcard matching
def compile_pattern(url, param_pattern='([^/]*)', strict=False):
    if url == '/':
        return re.compile('^\\/')

    params = []
    pattern = '^'
    url = urlparse(url).path

    for fragment in url.split('/'):
        if not fragment:
            continue
        pattern += '\\/+'

        param = PARAM_TEMPLATE_PATTERN.match(fragment)
        if param:
            (label,) = param.groups()
            params.append(label)
            pattern += PARAM_TEMPLATE_PATTERN.sub(param_pattern, fragment)
        else:
            pattern += fragment

    if strict and url[-1] == '/':
        pattern += '\\/'
    elif not strict:
        pattern += '[\\/]*'

    pattern += '$'

    return re.compile(pattern), params


class Router:
    def __init__(self):
        self.routes = []

    def route(self, *templates, methods=None):
        if not methods:
            methods = ['GET']

        def wrapper(func):
            route = Route(func)
            for template in templates:
                route.add_path(*compile_pattern(template), methods=methods)
            self.routes.append(route)
            return func

        return wrapper

    def match(self, req_event):
        for route in self.routes:
            params = route.match(req_event)
            if params:
                return route, params

        return None, None
