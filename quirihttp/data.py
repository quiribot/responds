class Request:
    def __init__(self, params, arg):
        self.params = params
        self.arg = arg


class Response:
    def __init__(self, arg):
        self.arg = arg


class DataFactory:
    def make_request(self, params, arg):
        return Request(params, arg)

    def make_response(self, arg):
        return Response(arg)
