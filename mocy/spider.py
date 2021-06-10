import inspect
import os
import time
from enum import Enum
from functools import partial
from queue import Queue
from threading import Thread, Lock
from typing import Optional, Generator, Any, Union, \
    MutableSequence, Sequence, Tuple, List, Callable, Iterable
from urllib.parse import urljoin, urlparse

import requests
from requests.exceptions import ConnectionError, Timeout

from .exceptions import (
    SpiderError,
    RequestIgnored,
    DownLoadError,
    ResponseIgnored,
    ParseError,
    PipeError,
    FailedStatusCode,
)
from .middlewares import random_useragent
from .request import Request
from .response import Response
from .utils import (
    logger,
    DelayQueue,
    random_range,
    identity,
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


class HandlerType(Enum):
    BEFORE_DOWNLOAD = 1
    AFTER_DOWNLOAD = 2
    PIPE = 3


def before_download(func):
    func._ht = HandlerType.BEFORE_DOWNLOAD
    return func


def after_download(func):
    func._ht = HandlerType.AFTER_DOWNLOAD
    return func


def pipe(func):
    func._ht = HandlerType.PIPE
    return func


class Spider:
    # The number of concurrent requests that will be performed by the downloader.
    WORKERS = os.cpu_count() * 2

    # The amount of time (in secs) that the downloader will wait before timeout.
    TIMEOUT = 30

    # The amount of time (in secs) that the downloader should wait before download.
    DOWNLOAD_DELAY = 0

    # If enabled, the downloader will wait a random time (0.5 * delay ~ 1.5 * delay by default)
    # before downloading the next page.
    RANDOM_DOWNLOAD_DELAY = True

    # Maximum number of times to retry when encountering connection issues or unexpected status codes.
    RETRY_TIMES = 3

    # HTTP response status codes to retry.
    # Other errors (DNS or connection issues) are always retried.
    # 502: Bad Gateway, 503: Service Unavailable, 504: Gateway Timeout
    # 408: Request Timeout, 429: Too Many Requests
    RETRY_CODES = (500, 502, 503, 504, 408, 429)

    # The amount of time (in secs) that the downloader will wait before retrying a failed request.
    RETRY_DELAY = 1

    MAX_REQUEST_QUEUE_SIZE = 256

    DEFAULT_HEADERS = {
        'User-Agent': 'mocy/0.1 (a kind spider)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-Hans-CN,zh-CN;q=0.9,zh;q=0.8,en;q=0.7,en-GB;q=0.6,en-US;q=0.5,'
                           'zh-TW;q=0.4,ja;q=0.3,pt;q=0.2,hu;q=0.1',
    }

    before_download_handlers: List[Callable] = [random_useragent]

    after_download_handlers: List[Callable] = []

    pipes: List[Callable] = []

    entry: Union[str, Request, Iterable[Union[str, Request]], Callable] = []

    def __init__(self) -> None:
        self._check_config()
        self._check_handlers()

        self._request_queue = DelayQueue(self.MAX_REQUEST_QUEUE_SIZE)
        self._response_queue = Queue()

        self._request_count = 0
        self._response_count = 0
        self._failed_urls = []

        self._last_download_time = 0
        self._lock = Lock()

    def on_start(self) -> None:
        """Called when the spider starts up."""

    def parse(self, res: Response) -> Any:
        """Parse a response and generate some data or new requests."""
        yield res

    def collect(self, item: Any) -> Any:
        """Called when the spider outputs a result.
        Usually it will be called multiple times。"""
        logger.info(item)

    def on_finish(self) -> None:
        """Called when the spider exits."""

    def on_error(self, reason: SpiderError) -> None:
        """Called when the spider encounters an error when downloading or parsing.
        It may be called multiple times。"""
        logger.error(reason.msg, exc_info=reason.cause)

    def start(self) -> None:
        """Starts up the spider.
        It will keep running until all requests were downloaded."""
        start = time.time()
        logger.info('Spider is running...')

        for item in self:
            error = None
            if not isinstance(item, SpiderError):
                try:
                    self._start_pipes(*item)
                except Exception as err:
                    req, res = item[1].req, item[1]
                    error = PipeError(req.url, err)
                    error.req, error.res = req, res
            else:
                error = item

            if not error:
                continue

            try:
                self.on_error(error)
            except Exception as err:
                logger.error('Error in error handler!', exc_info=err)

        logger.info('Spider exited; total running time {:.2f}s.'.format(time.time() - start))
        self._log_failed_urls()

    def __iter__(self) -> Generator[Union[SpiderError, Tuple[Any, requests.Response]], None, None]:
        self.on_start()
        self._start_requests()
        self._start_downloaders()

        while not self._completed:
            res = self._response_queue.get()
            self._response_count += 1

            if isinstance(res, SpiderError):
                err = self._check_error(res)
                if err:
                    yield err
                continue

            res.select = partial(Response.select, res)

            parse = getattr(res.req, 'callback') or self.parse

            session = res.session
            close_session = True

            try:
                result = parse(res)
                if isinstance(result, (MutableSequence, Generator)):
                    for item in result:
                        if isinstance(item, Request):
                            req = item
                            req.url = urljoin(res.url, req.url)

                            if session and (req.session in (False, None)):
                                close_session = False
                                req.session = session

                            req.headers['Referer'] = res.url
                            self._add_request(req)
                        else:
                            yield item, res
            except Exception as err:
                err = ParseError(res.req.url, err)
                err.req = res.req
                err.res = res
                yield err

            if session and close_session:
                session.close()

        self.on_finish()

    @classmethod
    def _check_config(cls) -> None:
        assert_positive_integer(cls.WORKERS)
        assert_positive_integer(cls.MAX_REQUEST_QUEUE_SIZE)
        assert_not_negative_integer(cls.RETRY_TIMES)
        assert_not_negative_number(cls.RETRY_DELAY)
        assert_not_negative_number(cls.DOWNLOAD_DELAY)

        for code in cls.RETRY_CODES:
            assert code in range(400, 600)

        timeout = cls.TIMEOUT
        if isinstance(timeout, Sequence):
            assert len(timeout) == 2
            for num in timeout:
                assert_positive_number(num)
        else:
            assert_positive_number(timeout)

        random_delay = cls.RANDOM_DOWNLOAD_DELAY
        assert isinstance(random_delay, (bool, Sequence))
        if isinstance(random_delay, Sequence):
            assert len(random_delay) == 2
            for num in random_delay:
                assert_positive_number(num)

    @classmethod
    def _check_handlers(cls) -> None:
        def check(handlers, name):
            for idx, handler in enumerate(handlers):
                if inspect.isfunction(handler):
                    return
                if hasattr(handler, name):
                    hdl = getattr(handler, name)
                else:
                    logger.warn('No `{}` handler in {}'.format(name, handler.__class__))
                    hdl = identity

                handlers[idx] = hdl

        check(cls.before_download_handlers, 'before_download')
        check(cls.after_download_handlers, 'after_download')

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
        self._request_count += 1

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
        for idx in range(self.WORKERS):
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
                err.req = req
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
                if isinstance(err.cause, (ConnectionError, Timeout, FailedStatusCode)):
                    err.need_retry = True
                err.req = req
                self._response_queue.put(err)
                continue

            # after download
            try:
                res = self._post_download(res)
            except Exception as err:
                if not isinstance(err, ResponseIgnored):
                    err = ResponseIgnored(res.req.url, err)
                err.req = req
                err.res = res
                self._response_queue.put(err)
                continue

            self._response_queue.put(res)

    @classmethod
    def _check_status_codes(cls, res: Response) -> None:
        if res.status_code in cls.RETRY_CODES:
            err = DownLoadError(res.req.url, FailedStatusCode(res.status_code))
            err.res = res
            raise err

    def _wait(self, delay) -> None:
        if delay <= 0:
            return

        with self._lock:
            rest = time.time() - self._last_download_time
            if delay > rest:
                time.sleep(delay - rest)
            self._last_download_time = time.time()

    @classmethod
    def _get_download_delay(cls) -> Union[int, float]:
        delay = cls.DOWNLOAD_DELAY
        if delay <= 0:
            return 0

        random = cls.RANDOM_DOWNLOAD_DELAY

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
            if inspect.isfunction(value) and hasattr(value, '_ht'):
                ht = getattr(value, '_ht')
                if ht == HandlerType.BEFORE_DOWNLOAD:
                    cls.before_download_handlers.append(value)
                elif ht == HandlerType.AFTER_DOWNLOAD:
                    cls.after_download_handlers.append(value)
                else:
                    cls.pipes.append(value)

    def _pre_download(self, req: 'Request') -> Optional['Request']:
        rv = req
        for handler in self.before_download_handlers:
            rv = handler(self, rv)
            if not isinstance(rv, Request):
                raise RequestIgnored(req.url)
        return rv

    def _post_download(self, res: 'Response') -> Optional[Union['Response', 'Request']]:
        rv = res
        for handler in self.after_download_handlers:
            rv = handler(self, rv)
            if not isinstance(rv, requests.Response):
                err = ResponseIgnored(res.req.url)
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

    def _check_error(self, error: SpiderError) -> Optional[SpiderError]:
        if isinstance(error, RequestIgnored):
            if error.cause:
                return error
            else:
                logger.debug(f'Request for {error.req.url} was ignored')
        elif isinstance(error, ResponseIgnored):
            if error.new_req:
                self._add_request(error.new_req)
            if error.cause:
                return error
            else:
                logger.debug(f'Response for {error.req.url} was ignored')
        elif isinstance(error, DownLoadError):
            req = error.req
            if error.need_retry and req.retry_num < self.RETRY_TIMES:
                req.retry_num += 1
                logger.debug('Retrying ({}) for {}...'.format(req.retry_num, req.url))
                self._add_request(req)
            else:
                self._failed_urls.append(req.url)
                return error

    def _log_failed_urls(self) -> None:
        urls = self._failed_urls
        if not urls:
            return

        num = len(urls)
        s = 's' if num > 1 else ''
        msg = 'Fail to download from the following {} url{}:\n{}'.format(num, s, '\n'.join(urls))
        logger.error(msg)

    @property
    def _completed(self) -> bool:
        return self._request_count == self._response_count
