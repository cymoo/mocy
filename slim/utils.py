import logging
import time
from queue import Queue, PriorityQueue
from threading import Lock, Thread
from typing import Optional


__all__ = [
    'DelayQueue',
    'DummyLock',
    'set_logger',
    'get_logger',
    'debug',
    'info',
    'warn',
    'error'
]


class DelayQueue(Queue):
    def __init__(self):
        super().__init__()
        self.pq = PriorityQueue()
        poller = Thread(target=self._poll, name='poller')
        poller.daemon = True
        poller.start()

    def put_later(self, item, delay=0):
        self.pq.put((time.time() + delay, item))

    def _poll(self):
        while True:
            item = self.pq.get()
            if item[0] <= time.time():
                self.put(item[1])
            else:
                self.pq.put(item)


class DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# logging utils
DEFAULT_LOGGER_NAME = 'spider'
DEFAULT_LOGGER_FORMAT = '[%(asctime)s] %(levelname)s: %(message)s'
DEFAULT_LOGGER_LEVEL = logging.INFO

_logger: Optional[logging.Logger] = None
_lock: Lock = Lock()


def set_logger(logger: logging.Logger) -> None:
    global _logger
    _logger = logger


def get_logger() -> logging.Logger:
    if _logger is None:
        _set_default_logger()
    return _logger


def _set_default_logger() -> None:
    global _logger
    with _lock:
        _logger = logging.getLogger(DEFAULT_LOGGER_NAME)
        formatter = logging.Formatter(DEFAULT_LOGGER_FORMAT)
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        _logger.addHandler(handler)
        _logger.setLevel(DEFAULT_LOGGER_LEVEL)


def log(level: int, msg: str, *args, **kw) -> None:
    logger = get_logger()
    logger.log(level, msg, *args, **kw)


def debug(msg: str, *args, **kw) -> None:
    log(logging.DEBUG, msg, *args, **kw)


def info(msg: str, *args, **kw) -> None:
    log(logging.INFO, msg, *args, **kw)


def warn(msg: str, *args, **kw) -> None:
    log(logging.WARNING, msg, *args, **kw)


def error(msg: str, *args, **kw) -> None:
    log(logging.ERROR, msg, *args, **kw)


class Logger:
    def __init__(self):
        pass

    def add_logger(self):
        pass

    def get_logger(self):
        pass

    def log(self):
        pass

    def debug(self):
        pass

    def info(self):
        pass

    def warn(self):
        pass

    def error(self):
        pass

    def critical(self):
        pass
