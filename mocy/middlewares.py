import random
import time
from typing import Sequence

from .request import Request
from .response import Response
from .utils import logger


user_agents_pc = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36 Edg/90.0.818.51',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.16; rv:78.0) Gecko/20100101 Firefox/78.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
    'Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; fr) Presto/2.9.168 Version/11.52',
]

user_agents_mobile = [
    'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1 Edg/90.0.4430.93',
    'Mozilla/5.0 (Linux; Android 10.0.0; Pixel 2 XL Build/OPD1.170816.004) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Mobile Safari/537.36 Edg/90.0.818.51',
    'Mozilla/5.0 (iPad; CPU OS 11_0 like Mac OS X) AppleWebKit/604.1.34 (KHTML, like Gecko) Version/11.0 Mobile/15A5341f Safari/604.1 Edg/90.0.4430.93',
    'Mozilla/5.0 (Linux; U; Android 10; zh-CN; TAS-AL00 Build/HUAWEITAS-AL00) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/78.0.3904.108 UCBrowser/13.3.6.1116 Mobile Safari/537.36',
]


class RandomUserAgent:
    def __init__(self, type='pc'):
        self.type = type

    def before_download(self, spider, req):
        ua_pc = random.choice(user_agents_pc)
        ua_mobile = random.choice(user_agents_mobile)
        if self.type == 'pc':
            ua = ua_pc
        elif self.type == 'mobile':
            ua = ua_mobile
        else:
            ua = random.choice([ua_pc, ua_mobile])
        req.headers.setdefault('User-Agent', ua)
        return req


def random_useragent(spider, req):
    req.headers['User-Agent'] = random.choice(user_agents_pc)
    return req


def robottxt(spider, req):
    raise NotImplementedError


class Retry:
    def __init__(self, http_codes: Sequence[int]):
        self.http_codes = http_codes

    def after_download(self, spider, res: Response):
        pass


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
