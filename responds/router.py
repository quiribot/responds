import re
from urllib.parse import urlparse


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

        if fragment[0] == '<' and fragment[-1] == '>':
            label = fragment[1:-1]
            params.append(label)
            pattern += param_pattern
        else:
            pattern += fragment

    if strict and url[-1] == '/':
        pattern += '\\/'
    elif not strict:
        pattern += '[\\/]*'

    pattern += '$'

    return re.compile(pattern), params


class Params:
    def __init__(self, groups, params):
        # TODO: Edge case where len(groups) > len(params) or otherwise
        self._params = dict(zip(params, groups))

    def __getattr__(self, attr):
        try:
            return self._params[attr]
        except KeyError as e:
            raise AttributeError() from e


class Route:
    def __init__(self, handler, methods, params):
        self.handler = handler
        self.methods = methods
        self.params = params


class Router:
    def __init__(self):
        self.routes = []

    def route(self, template, methods=None):
        if not methods:
            methods = ['GET']

        def wrapper(func):
            self.routes.append(compile_pattern(template) + (func, methods))
            return func

        return wrapper

    def match(self, path, req_arg=None, res_arg=None):
        for exp, params, handler, methods in self.routes:
            match = exp.match(path)
            if not match:
                continue
            return Route(handler, methods, Params(match.groups(), params))

        return None
