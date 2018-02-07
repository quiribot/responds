from quirihttp.data import DataFactory
from quirihttp.router import Router

r = Router(DataFactory())


@r.route('/hey/this/is/cool')
def cool(req, res):
    print('It works!!!')


@r.route('/hello/<param>')
def hello(req, res):
    print('We have parameters, too: param={}'.format(req.params.param))


assert r.match('/hey/this/is/cool')
assert r.match('/hello/yes')
