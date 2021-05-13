
__all__ = [
    'random_useragent',
    'download_stats',
]


def random_useragent(spider, request):
    return request


def download_stats(spider, request):
    return request


def robottxt(spider, request):
    raise NotImplementedError

