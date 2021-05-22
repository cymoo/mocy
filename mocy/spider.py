import inspect
import os
import time
from enum import Enum
from functools import partial
from queue import Queue
from threading import Thread, Lock
from typing import Optional, Generator, Any, Union, MutableSequence, Sequence
from urllib.parse import urljoin, urlparse

import requests
from requests.exceptions import ConnectionError, Timeout

from .exceptions import (
    SpiderError,
    DownLoadError,
    ParseError,
    RequestIgnored,
    ResponseIgnored
)
from .middlewares import random_useragent
from .request import Request
from .response import Response
from .utils import (
    logger,
    DelayQueue,
    random_range,
    assert_positive_integer,
    assert_not_negative_integer,
    assert_positive_number,
    assert_not_negative_number,
)

__all__ = [
    'Spider',
    'before_download',
    'after_download',
    'pipe',
]


class Hook(Enum):
    BEFORE_DOWNLOAD = 1
    AFTER_DOWNLOAD = 2
    PIPE = 3


def before_download(func):
    func._hook_type = Hook.BEFORE_DOWNLOAD
    return func


def after_download(func):
    func._hook_type = Hook.AFTER_DOWNLOAD
    return func


def pipe(func):
    func._hook_type = Hook.PIPE
    return func


class Spider:
    # The maximum number of concurrent requests that will be performed by the downloader.
    WORKERS = os.cpu_count() * 2

    # The amount of time (in secs) that the downloader will wait before timeout.
    TIMEOUT = 30

    # The amount of time (in secs) that the downloader should wait
    # before downloading consecutive pages from the same website.
    DOWNLOAD_DELAY = 0

    # If enabled, the spider will wait a random time (between 0.5 * delay and 1.5 * delay)
    # while fetching requests from the same website.
    RANDOM_DOWNLOAD_DELAY = True

    # Maximum number of times to retry.
    RETRY_TIMES = 3

    # HTTP response codes to retry.
    # Other errors (DNS or connection issues) are always retried.
    # 502: Bad Gateway
    # 503: Service Unavailable
    # 504: Gateway Timeout
    # 408: Request Timeout
    # 429: Too Many Requests
    RETRY_CODES = [500, 502, 503, 504, 408, 429]

    # The amount of time (in secs) that the downloader will wait
    # before retrying a failed request.
    RETRY_DELAY = 3

    MAX_REQUEST_QUEUE_SIZE = 256

    DEFAULT_HEADERS = {
        'User-Agent': 'mocy'
    }

    before_download_handlers = [random_useragent]

    after_download_handlers = []

    pipes = []

    entry = []

    def __init__(self) -> None:
        self._check_config()

        self._request_queue = DelayQueue(self.MAX_REQUEST_QUEUE_SIZE)
        self._response_queue = Queue()

        self._request_num = 0
        self._response_num = 0
        self._failed_urls = []

        self._last_download_time = 0
        self._lock = Lock()

    def on_start(self) -> None:
        pass

    def parse(self, res: 'Response') -> Any:
        yield res

    def collect(self, item: Any) -> Any:
        logger.info(item)

    def on_finish(self) -> None:
        pass

    def on_error(self, reason: SpiderError) -> None:
        logger.error(reason.msg, exc_info=reason.cause)

    def start(self):
        start = time.time()
        logger.info('Spider is running...')

        self.on_start()
        self._start_requests()
        self._start_downloaders()

        default_parser = getattr(self, 'parse')

        while not self._completed:
            res = self._response_queue.get()
            self._response_num += 1

            if not self._ensure_valid_response(res):
                continue

            res.select = partial(Response.select, res)

            parser = res.callback if res.callback else default_parser

            session = res.session
            close_session = True

            try:
                result = parser(res)
                if isinstance(result, (MutableSequence, Generator)):
                    for item in parser(res):
                        if isinstance(item, Request):
                            if session and item.session is False:
                                close_session = False
                                item.session = res.session

                            item.url = urljoin(res.url, item.url)
                            self._add_request(item)
                        else:
                            self._start_pipes(item, res)
            except Exception as err:
                err = ParseError(res.url, err)
                err.res = res
                self.on_error(err)

            if session and close_session:
                try:
                    session.close()
                except Exception as err:
                    err = SpiderError('Cannot close session', err)
                    self.on_error(err)

        logger.info('Spider exited; running time: {:.2f}s.'.format(time.time() - start))
        self._log_failed_urls()
        self.on_finish()

    def _check_config(self):
        assert_positive_integer(self.WORKERS)
        assert_positive_integer(self.MAX_REQUEST_QUEUE_SIZE)
        assert_not_negative_integer(self.RETRY_TIMES)
        assert_not_negative_number(self.RETRY_DELAY)
        assert_not_negative_number(self.DOWNLOAD_DELAY)

        for http_code in self.RETRY_CODES:
            assert http_code in range(400, 600)

        timeout = self.TIMEOUT
        if isinstance(timeout, Sequence):
            assert len(timeout) == 2
            for num in timeout:
                assert_positive_number(num)
        else:
            assert_positive_number(timeout)

        random_delay = self.RANDOM_DOWNLOAD_DELAY
        assert isinstance(random_delay, (bool, Sequence))
        if isinstance(random_delay, Sequence):
            assert len(random_delay) == 2
            for num in random_delay:
                assert_positive_number(num)

    def _start_requests(self) -> None:
        entry = self.entry
        if inspect.ismethod(entry):
            entry = entry()

        if isinstance(entry, (str, Request)):
            entry = [entry]

        for req in entry:
            assert isinstance(req, (str, Request))
            if not isinstance(req, Request):
                req = Request(req)
            self._add_request(req)

    def _add_request(self, req: 'Request') -> None:
        self._request_num += 1

        if req.timeout is None:
            req.timeout = self.TIMEOUT

        self._add_default_header(req)

        if req.retry_num > 0 and self.RETRY_DELAY > 0:
            self._request_queue.put_later(req, self.RETRY_DELAY)
        else:
            self._request_queue.put(req)

    def _add_default_header(self, req: Request) -> None:
        headers = req.headers
        headers.setdefault('Host', urlparse(req.url).netloc)
        for name, value in self.DEFAULT_HEADERS.items():
            headers.setdefault(name, value)

    def _start_downloaders(self) -> None:
        for idx in range(max(self.WORKERS, 1)):
            thread = Thread(target=self._download, name='downloader-{}'.format(idx))
            thread.daemon = True
            thread.start()

    def _download(self) -> None:
        while True:
            req = self._request_queue.get()

            self._wait(self._get_download_delay())

            # before download
            try:
                req = self._pre_download(req)
            except Exception as err:
                if not isinstance(err, RequestIgnored):
                    err = RequestIgnored(req.url, err)
                self._response_queue.put(err)
                continue

            # downloading
            try:
                t0 = time.time()
                res = req.send()
                t1 = time.time()
                logger.info('"{} {}" {} {:.2f}s'.format(
                    req.method, req.url, res.status_code, t1 - t0
                ))
                self._check_status_codes(res)

            except Exception as err:
                if not isinstance(err, DownLoadError):
                    err = DownLoadError(req.url, err)
                if isinstance(err.cause, (ConnectionError, Timeout)):
                    err.retry_req = req
                self._response_queue.put(err)
                continue

            # after download
            try:
                res = self._post_download(res)
            except Exception as err:
                if not isinstance(err, ResponseIgnored):
                    err = ResponseIgnored(res.url, err)
                self._response_queue.put(err)
                continue

            self._response_queue.put(res)

    def _check_status_codes(self, res: Response) -> None:
        if res.status_code in self.RETRY_CODES:
            err = DownLoadError(url=res.url)
            err.retry_req = res.req
            raise err

    def _wait(self, delay) -> None:
        if delay <= 0:
            return

        with self._lock:
            rest = time.time() - self._last_download_time
            if delay > rest:
                time.sleep(delay - rest)
            self._last_download_time = time.time()

    def _get_download_delay(self) -> Union[int, float]:
        delay = self.DOWNLOAD_DELAY
        if delay <= 0:
            return 0

        random = self.RANDOM_DOWNLOAD_DELAY

        if not random:
            return delay

        if random is True:
            s1, s2 = 0.5, 1.5
        else:
            s1, s2 = random

        return random_range(delay, s1, s2)

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if vars(cls).get('before_download_handlers') is None:
            cls.before_download_handlers = Spider.before_download_handlers.copy()
        if vars(cls).get('after_download_handlers') is None:
            cls.after_download_handlers = Spider.after_download_handlers.copy()
        if vars(cls).get('pipes') is None:
            cls.pipes = Spider.pipes.copy()

        # class attribute definition order is preserved from 3.6
        for value in cls.__dict__.values():
            if inspect.isfunction(value) and hasattr(value, '_hook_type'):
                ht = getattr(value, '_hook_type')
                if ht == Hook.BEFORE_DOWNLOAD:
                    cls.before_download_handlers.append(value)
                elif ht == Hook.AFTER_DOWNLOAD:
                    cls.after_download_handlers.append(value)
                else:
                    cls.pipes.append(value)

    def _pre_download(self, req: 'Request') -> Optional['Request']:
        rv = req
        for handler in self.before_download_handlers:
            if not inspect.isfunction(handler):
                if hasattr(handler, 'before_download'):
                    handler = getattr(handler, 'before_download')
                else:
                    logger.warn('No `before_download` handler in {}.'.format(handler.__class__))
                    continue
            rv = handler(self, rv)
            if not isinstance(rv, Request):
                raise RequestIgnored(req.url)
        return rv

    def _post_download(self, res: 'Response') -> Optional[Union['Response', 'Request']]:
        rv = res
        for handler in self.after_download_handlers:
            if not inspect.isfunction(handler):
                if hasattr(handler, 'after_download'):
                    handler = getattr(handler, 'after_download')
                else:
                    logger.warn('No `after_download` handler in {}.'.format(handler.__class__))
                    continue
            rv = handler(self, rv)
            if not isinstance(rv, requests.Response):
                err = ResponseIgnored(res.url)  # or res.req.url?
                if isinstance(rv, Request):
                    err.new_req = rv
                raise err
        return rv

    def _start_pipes(self, item: Any, res: 'Response') -> Any:
        rv = item
        for func in (self.pipes or (self.__class__.collect,)):
            arg_count = func.__code__.co_argcount
            if arg_count == 3:
                rv = func(self, rv, res)
            else:
                rv = func(self, rv)

            if rv is None:
                return None
        return rv

    def _ensure_valid_response(self, res: Union[SpiderError, requests.Response]) -> bool:
        if isinstance(res, requests.Response):
            return True

        if isinstance(res, RequestIgnored):
            pass
        elif isinstance(res, DownLoadError):
            req = res.retry_req
            if req.retry_num <= self.RETRY_TIMES:
                req.retry_num += 1
                logger.error('Retry (num={}) {}'.format(req.retry_num, req.url))
                self._add_request(req)
            else:
                self._failed_urls.append(req.url)
        elif isinstance(res, ResponseIgnored):
            if res.new_req:
                self._add_request(res.new_req)

        try:
            self.on_error(res)
        except Exception as err:
            logger.error('Error in error handler!', exc_info=err)

        return False

    def _log_failed_urls(self) -> None:
        urls = self._failed_urls
        if not urls:
            return

        num = len(urls)
        s = 's' if num > 1 else ''
        msg = 'Cannot download from {} url{}:\n{}'.format(num, s, '\n'.join(urls))
        logger.info(msg)

    @property
    def _completed(self) -> bool:
        return self._request_num == self._response_num
