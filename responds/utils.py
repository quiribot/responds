import re
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
            (label, ) = param.groups()
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
