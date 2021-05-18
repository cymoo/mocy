import inspect
import os
import time
from functools import partial
from queue import Queue
from threading import Thread, Lock
from typing import Optional, Generator, Any, Union, MutableSequence, Sequence
from urllib.parse import urljoin, urlparse

import requests

from .exceptions import (
    SpiderError,
    DownLoadError,
    ParseError,
    RequestIgnored,
    ResponseIgnored
)
from .middlewares import (
    random_useragent,
    DownloadStats,
)
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


def before_download(func):
    func._hook_type = 1
    return func


def after_download(func):
    func._hook_type = 2
    return func


def pipe(func):
    func._hook_type = 3
    return func


class Spider:
    # The maximum number of concurrent requests that will be performed by the downloader.
    workers = os.cpu_count() * 2

    # The amount of time (in secs) that the downloader will wait before timeout.
    download_timeout = 30

    # The amount of time (in secs) that the downloader should wait
    # before downloading consecutive pages from the same website.
    download_delay = 0

    # If enabled, the spider will wait a random time (between 0.5 * delay and 1.5 * delay)
    # while fetching requests from the same website.
    random_download_delay = True

    # Maximum number of times to retry.
    retry_times = 3

    # The amount of time (in secs) that the downloader will wait
    # before retrying a failed request.
    retry_delay = 3

    # HTTP response codes to retry.
    # Other errors (DNS or connection issues, etc) are always retried.
    retry_http_codes = [500, 502, 503, 504, 522, 524, 408, 429]

    max_request_queue_size = 512

    default_headers = {
        'User-Agent': 'mocy'
    }

    before_download_handlers = [DownloadStats(), random_useragent]

    after_download_handlers = [DownloadStats()]

    pipes = []

    entry = []

    def __init__(self) -> None:
        self._check_config()

        self._request_queue = DelayQueue(self.max_request_queue_size)
        self._response_queue = Queue()

        self._all_requests = 0
        self._all_responses = 0
        self._failed_urls = []

        self._last_download_time = 0
        self._lock = Lock()

    def parse(self, res: 'Response') -> Generator:
        yield res

    def collect(self, item: Any) -> Any:
        logger.info(item)

    def on_finish(self) -> None:
        pass

    def on_error(self, reason: SpiderError) -> None:
        logger.error(reason.msg, exc_info=reason.cause)

    def before_start(self) -> None:
        pass

    def start(self):
        start = time.time()
        logger.info('Spider is running...')

        self.before_start()
        self._start_requests()
        self._start_downloaders()

        default_parser = getattr(self, 'parse')

        while not self._completed:
            res = self._response_queue.get()
            self._all_responses += 1

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
        assert_positive_integer(self.workers)
        assert_positive_integer(self.max_request_queue_size)
        assert_not_negative_integer(self.retry_times)
        assert_not_negative_number(self.retry_delay)
        assert_not_negative_number(self.download_delay)

        for http_code in self.retry_http_codes:
            assert http_code in range(400, 600)

        timeout = self.download_timeout
        if isinstance(timeout, Sequence):
            assert len(timeout) == 2
            for num in timeout:
                assert_positive_number(num)
        else:
            assert_positive_number(timeout)

        random_delay = self.random_download_delay
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

    def _add_request(self, req: 'Request', delay: Union[int, float] = 0) -> None:
        # req.retry = self.retry_times
        # req.timeout = self.download_timeout
        self._all_requests += 1
        self._add_default_header(req)
        if delay > 0:
            self._request_queue.put_later(req, delay)
        else:
            self._request_queue.put(req)

    def _add_default_header(self, req: Request) -> None:
        headers = req.headers
        headers.setdefault('Host', urlparse(req.url).netloc)
        for name, value in self.default_headers.items():
            headers.setdefault(name, value)

    def _start_downloaders(self):
        for idx in range(max(self.workers, 1)):
            thread = Thread(target=self._download, name='downloader-{}'.format(idx))
            thread.daemon = True
            thread.start()

    def _download(self):
        while True:
            req = self._request_queue.get()

            if self.download_delay > 0:
                self._wait()

            try:
                req = self._pre_download(req)
            except Exception as err:
                if not isinstance(err, RequestIgnored):
                    err = RequestIgnored(req.url, err)
                self._response_queue.put(err)
                continue

            try:
                res = req.send()
            except Exception as err:
                err = DownLoadError(req.url, err)
                err.retry_req = req
                self._response_queue.put(err)
                continue

            try:
                res = self._post_download(res)
            except Exception as err:
                if not isinstance(err, ResponseIgnored):
                    err = ResponseIgnored(res.url, err)
                self._response_queue.put(err)
                continue

            self._response_queue.put(res)

    def _wait(self):
        if self.random_download_delay:
            delay = self._random_delay()
        else:
            delay = self.download_delay

        with self._lock:
            rest = time.time() - self._last_download_time
            if delay > rest:
                time.sleep(delay - rest)
            self._last_download_time = time.time()

    def _random_delay(self):
        random_delay = self.random_download_delay
        if isinstance(random_delay, bool):
            s1, s2 = 0.5, 1.5
        else:
            s1, s2 = random_delay
        return random_range(self.download_delay, s1, s2)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, 'before_download_handlers'):
            cls.before_download_handlers = Spider.before_download_handlers.copy()
        if not hasattr(cls, 'after_download_handlers'):
            cls.after_download_handlers = Spider.after_download_handlers.copy()
        if not hasattr(cls, 'pipes'):
            cls.pipes = Spider.pipes.copy()

        # class attribute definition order is preserved from 3.6
        for value in cls.__dict__.values():
            if inspect.isfunction(value) and hasattr(value, '_hook_type'):
                t = getattr(value, '_hook_type')
                if t == 1:
                    cls.before_download_handlers.append(value)
                elif t == 2:
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
                err = ResponseIgnored(res.url)
                if isinstance(rv, Request): err.new_req = rv
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
            if req.retry > 0:
                req.retry -= 1
                # TODO: a retry delay?
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
        if not urls: return

        num = len(urls)
        s = 's' if num > 1 else ''
        msg = 'Cannot download from {} url{}:\n{}'.format(num, s, '\n'.join(urls))
        logger.info(msg)

    @property
    def _completed(self) -> bool:
        return self._all_requests == self._all_responses
