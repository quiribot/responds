import inspect


class Params:
    def __init__(self, groups, params):
        # TODO: Edge case where len(groups) > len(params) or otherwise
        self._params = dict(zip(params, groups))

    def __getattr__(self, attr):
        try:
            return self._params[attr]
        except KeyError as e:
            raise AttributeError() from e


class Route(object):
    def __init__(self, fun):
        if not callable(fun):
            raise Exception('fun should be a callable')

        self.fun = fun
        self.paths = []

    def add_path(self, pattern, params, methods=None):
        if not methods:
            methods = ['GET']
        methods = [method.encode('ascii') for method in methods]

        self.paths.append((pattern, params, methods))

    def match(self, req_event):
        # NOTE: We could optimize this further by only matching
        # a single method at a time (no `not in` call), but
        # that'd require matching multiple patterns that are
        # (likely) the same
        for pattern, params, methods in self.paths:
            matches = pattern.match(req_event.target.decode('utf-8'))
            if not matches:
                continue
            if req_event.method not in methods:
                continue
            return Params(matches.groups(), params)
        return None

    async def call(self, *args, **kwargs):
        res = self.fun(*args, **kwargs)
        if inspect.isawaitable(res):
            res = await res
        return res
