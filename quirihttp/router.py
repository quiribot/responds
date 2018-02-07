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
        self._params = dict(zip(params, groups))

    def __getattr__(self, attr):
        try:
            return self._params[attr]
        except KeyError as e:
            raise AttributeError() from e


# def build_param_dict(groups, params):
#     TODO: Edge case where len(groups) > len(params) or otherwise
#     return dict(zip(params, groups))
#     out = {}
#     params_i = len(params) - 1
#     for i, param in enumerate(groups):
#         if i > params_i:
#             break
#         out[params[i]] = param

#     return out


class Router:
    def __init__(self, http_factory):
        self.routes = []
        self.http_factory = http_factory

    def route(self, template, methods=None):
        if not methods:
            methods = ['GET']

        def wrapper(func):
            self.routes.append(compile_pattern(template) + (func,))
            return func

        return wrapper

    def match(self, path, req_arg=None, res_arg=None):
        for exp, params, handler in self.routes:
            match = exp.match(path)
            if not match:
                continue
            req = self.http_factory.make_request(Params(match.groups(), params), req_arg)
            res = self.http_factory.make_response(res_arg)
            handler(req, res)
            return True

        return False
