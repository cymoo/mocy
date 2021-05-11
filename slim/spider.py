import os
import time
from functools import partial
from queue import Queue
from threading import Thread, Lock
from typing import Optional, Generator, Any, Union

import requests

from .utils import info, error, DummyLock, DelayQueue
from .exceptions import (
    SpiderError,
    DownLoadError,
    ParseError,
    RequestIgnored,
    ResponseIgnored
)
from .request import Request
from .response import Response

__all__ = [
    'Spider',
    'before_download',
    'after_download',
    'pipe',
    'before_download_handlers',
    'after_download_handlers',
    'pipes',
]


before_download_handlers = []
after_download_handlers = []
pipes = []


def before_download(func):
    before_download_handlers.append(func)
    return func


def after_download(func):
    after_download_handlers.append(func)
    return func


def pipe(func):
    pipes.append(func)
    return func


class Spider:
    config = {
        'workers': os.cpu_count() * 2,
        'timeout': 3,
        'delay': 0,
        'retry': 3,
        'lock': False,
    }

    entry = []

    def __init__(self) -> None:
        self._merge_configs()

        self._request_queue = DelayQueue()
        self._response_queue = Queue()

        self._all_requests = 0
        self._all_responses = 0
        self._failed_urls = []

        self._lock = Lock() if self.config['lock'] else DummyLock()

    def parse(self, res: 'Response') -> Generator:
        yield res

    def collect(self, item: Any) -> Any:
        info(item)

    def handle_error(self, reason: SpiderError) -> None:
        error(reason.msg, exc_info=reason.cause)

    def start(self):
        start = time.time()
        info('Spider is running...')
        default_parser = getattr(self, 'parse')

        self._init_requests()
        self._init_fetchers()

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
                for item in parser(res):
                    if isinstance(item, Request):
                        if session and item.session is False:
                            close_session = False
                            item.session = res.session
                        self._add_request(item)
                    else:
                        self._process_pipes(item, res)
            except Exception as err:
                err = ParseError(res.url, err)
                err.res = res
                self.handle_error(err)

            if session and close_session:
                try:
                    session.close()
                except Exception as err:
                    err = SpiderError('Cannot close session', err)
                    self.handle_error(err)

        info('Spider exited; running time: {:.1f}s.'.format(time.time() - start))
        self._log_failed_urls()

    def _merge_configs(self) -> None:
        cfg = Spider.config.copy()
        cfg.update(vars(self.__class__).get('config', {}))
        self.config = cfg

    def _process_before_download(self, req: 'Request') -> Optional['Request']:
        rv = req
        for func in before_download_handlers:
            with self._lock:
                rv = func(self, rv)
            if not isinstance(rv, Request):
                raise RequestIgnored(req.url)
        return rv

    def _process_after_download(self, res: 'Response') -> Optional[Union['Response', 'Request']]:
        rv = res
        for func in after_download_handlers:
            with self._lock:
                rv = func(self, rv)
            if not isinstance(rv, Response):
                err = ResponseIgnored(res.url)
                if isinstance(rv, Request): err.new_req = rv
                raise err
        return rv

    def _process_pipes(self, item: Any, res: 'Response') -> Any:
        rv = item
        for func in (pipes or (self.__class__.collect,)):
            arg_count = func.__code__.co_argcount
            if arg_count == 3:
                rv = func(self, rv, res)
            else:
                rv = func(self, rv)

            if rv is None:
                return None
        return rv

    def _download(self):
        while True:
            req = self._request_queue.get()

            try:
                req = self._process_before_download(req)
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
                res = self._process_after_download(res)
            except Exception as err:
                if not isinstance(err, ResponseIgnored):
                    err = ResponseIgnored(res.url, err)
                self._response_queue.put(err)
                continue

            self._response_queue.put(res)

    def _init_fetchers(self):
        for idx in range(max(self.config['workers'], 1)):
            thread = Thread(target=self._download, name='fetcher-{}'.format(idx))
            thread.daemon = True
            thread.start()

    def _init_requests(self) -> None:
        entry = self.entry
        if isinstance(entry, str):
            entry = [entry]
        for req in entry:
            if not isinstance(req, Request):
                req = Request(req)
            self._add_request(req)

    def _add_request(self, req: 'Request', delay: Union[float, int] = 0) -> None:
        req.retry = self.config['retry']
        req.timeout = self.config['timeout']
        self._all_requests += 1
        if delay > 0:
            self._request_queue.put_later(req, delay)
        else:
            self._request_queue.put(req)

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
            self.handle_error(res)
        except Exception as err:
            error('Error in error handler!', exc_info=err)

        return False

    def _log_failed_urls(self) -> None:
        urls = self._failed_urls
        if not urls: return

        num = len(urls)
        s = 's' if num > 1 else ''
        msg = 'Cannot download from {} url{}:\n{}'.format(num, s, '\n'.join(urls))
        info(msg)

    @property
    def _completed(self) -> bool:
        return self._all_requests == self._all_responses
