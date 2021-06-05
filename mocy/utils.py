import logging
import re
import sys
import time
from queue import Queue, PriorityQueue
from random import random, randint
from threading import Thread
from typing import Union
from urllib.parse import urlparse

__all__ = [
    'DelayQueue',
    'logger',
    'random_range',
    'random_ip',
    'same_origin',
    'identity',
    'assert_positive_number',
    'assert_not_negative_number',
    'assert_positive_integer',
    'assert_not_negative_integer',
]


class DelayQueue(Queue):
    def __init__(self, maxsize=0):
        super().__init__(maxsize)
        self.pq = PriorityQueue()
        poller = Thread(target=self._poll, name='poller')
        poller.daemon = True
        poller.start()

    def put_later(self, item, delay=1):
        self.pq.put((time.time() + delay, item))

    def _poll(self):
        while True:
            item = self.pq.get()
            if item[0] <= time.time():
                self.put(item[1])
            else:
                self.pq.put(item)
                time.sleep(0.05)


def random_range(
        value: Union[int, float],
        scale1: Union[int, float],
        scale2: Union[int, float]
) -> float:
    if scale1 > scale2:
        lo, hi = scale2, scale1
    else:
        lo, hi = scale1, scale2
    factor = lo + (hi - lo) * random()
    return factor * value


def identity(x):
    return x


def assert_not_negative_number(num):
    assert num >= 0 and isinstance(num, (int, float))


def assert_positive_number(num):
    assert num > 0 and isinstance(num, (int, float))


def assert_not_negative_integer(num):
    assert num >= 0 and isinstance(num, int)


def assert_positive_integer(num):
    assert num > 0 and isinstance(num, int)


def add_http_if_no_scheme(url: str) -> str:
    """Add http as the default scheme if it is missing from the url."""
    match = re.match(r'^\w+://', url, flags=re.I)
    if not match:
        parts = urlparse(url)
        scheme = "http:" if parts.netloc else "http://"
        url = scheme + url
    return url


def same_origin(url1: str, url2: str) -> bool:
    """Return True if the two urls are the same origin
    >>> same_origin('http://a.com', 'https://a.com')
    False
    >>> same_origin('https://a.com', 'https://a.com:8080')
    False
    >>> same_origin('https://a.com/foo', 'https://a.com/bar')
    True
    """
    return all(map(
        lambda x: x[0] == x[1],
        list(zip(urlparse(url1), urlparse(url2)))[0:2]
    ))


def random_ip() -> str:
    """A simple ipv4 generator that filters some special ips."""
    specials = [0, 10, 100, 127, 172, 192, 198, 203, 224, 240, 255]

    def gen(): return randint(0, 255)

    while True:
        prefix = gen()
        if prefix not in specials:
            break
    return '.'.join(map(str, (prefix, gen(), gen(), gen())))


class Logger:
    logger_format = '[%(asctime)-15s] %(levelname)-7s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    def __init__(self, name: str, level: int = logging.DEBUG) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._add_stream_handlers()

    def replace(self, new_logger: logging.Logger) -> None:
        self._logger = new_logger

    def set_level(self, level: int) -> None:
        self._logger.setLevel(level)

    def add_handler(self, handler: logging.Handler) -> None:
        self._logger.addHandler(handler)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._logger.info(msg, *args, **kwargs)

    def warn(self, msg: str, *args, **kwargs) -> None:
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._logger.error(msg, *args, **kwargs)

    def _add_stream_handlers(self):
        stdout_handler = self._stream_handler(
            sys.stdout,
            logging.DEBUG,
            lambda record: record.levelno < logging.ERROR
        )
        stderr_handler = self._stream_handler(
            sys.stderr,
            logging.ERROR
        )
        self._logger.addHandler(stdout_handler)
        self._logger.addHandler(stderr_handler)

    def _stream_handler(self, stream, level, msg_filter=None):
        handler = logging.StreamHandler(stream)
        handler.setLevel(level)
        formatter = logging.Formatter(self.logger_format, datefmt=self.date_format)
        handler.setFormatter(formatter)
        if msg_filter:
            handler.addFilter(msg_filter)
        return handler


logger = Logger('mocy')
