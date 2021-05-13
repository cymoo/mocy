
__all__ = [
    'raise_http_error'
]


def raise_http_error(spider, response):
    response.raise_for_status()
    return response
