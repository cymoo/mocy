import random
import time
from mocy.utils import logger


user_agents = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36 Edg/90.0.818.51',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.16; rv:78.0) Gecko/20100101 Firefox/78.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
    'Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; fr) Presto/2.9.168 Version/11.52',
]


def random_useragent(spider, req):
    req.headers['User-Agent'] = random.choice(user_agents)
    return req


def robottxt(spider, req):
    raise NotImplementedError


def raise_http_error(spider, res):
    res.raise_for_status()
    return res


class DownloadStats:
    def before_download(self, spider, req):
        req.start_time = time.time()
        return req

    def after_download(self, spider, res):
        end_time = time.time()
        req = res.req
        logger.info('"{} {}" {} {:.2f}s'.format(
            req.method,
            req.url,
            res.status_code,
            end_time - req.start_time
        ))
        return res
