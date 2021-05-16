import functools
import inspect
import logging
import re
import sys
import time
from queue import Queue, PriorityQueue
from random import random
from typing import Union
from threading import Thread
from urllib.parse import urlparse


__all__ = [
    'DelayQueue',
    'get_enclosing_class',
    'logger',
    'random_range',
]


class DelayQueue(Queue):
    def __init__(self):
        super().__init__()
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


def get_enclosing_class(meth):
    """Get the class that defined a method.
    Refer to: https://stackoverflow.com/questions/3589311/get-defining-class-of-unbound-method-object-in-python-3/25959545#25959545

    >>> Logger == get_enclosing_class(Logger.info)
    True
    """

    if isinstance(meth, functools.partial):
        return get_enclosing_class(meth.func)

    if inspect.ismethod(meth) or (
            inspect.isbuiltin(meth)
            and getattr(meth, '__self__', None) is not None
            and getattr(meth.__self__, '__class__', None)
    ):
        for cls in inspect.getmro(meth.__self__.__class__):
            if meth.__name__ in cls.__dict__:
                return cls
        # fallback to __qualname__ parsing
        meth = getattr(meth, '__func__', meth)

    if inspect.isfunction(meth):
        cls = getattr(
            inspect.getmodule(meth),
            meth.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0],
            None
        )
        if isinstance(cls, type):
            return cls

    # handle special descriptor objects
    return getattr(meth, '__objclass__', None)


def random_range(value, scale1, scale2) -> float:
    if scale1 > scale2:
        lo, hi = scale2, scale1
    else:
        lo, hi = scale1, scale2
    factor = lo + (hi - lo) * random()
    return factor * value


def add_http_if_no_scheme(url):
    """Add http as the default scheme if it is missing from the url."""
    match = re.match(r'^\w+://', url, flags=re.I)
    if not match:
        parts = urlparse(url)
        scheme = "http:" if parts.netloc else "http://"
        url = scheme + url
    return url


class Logger:
    logger_format = '[%(asctime)-15s] %(levelname)-7s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    def __init__(self, name: str, level: int = logging.INFO) -> None:
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
