import os
import time
from functools import partial
from queue import Queue
from threading import Thread
from typing import Optional, Callable, Generator, Any, Union, List

import bs4
import requests
from bs4 import BeautifulSoup

import logger


class SpiderError(Exception):
    def __init__(self, msg: str, cause: Optional[Exception] = None) -> None:
        self.msg = msg
        self.cause = cause
        self.req = None
        self.res = None


class RequestIgnored(SpiderError):
    def __init__(self, url: str, cause: Optional[Exception] = None) -> None:
        super().__init__('Request was ignored: {}'.format(url), cause)


class ResponseIgnored(SpiderError):
    def __init__(self, url: str, cause: Optional[Exception] = None) -> None:
        self.new_req = None
        super().__init__('Response was ignored: {}'.format(url), cause)


class DownLoadError(SpiderError):
    def __init__(self, url: str, cause: Optional[Exception] = None) -> None:
        self.retry_req = None
        super().__init__('Cannot download from: {}'.format(url), cause)


class ParseError(SpiderError):
    def __init__(self, url: str, cause: Optional[Exception] = None) -> None:
        super().__init__('Cannot parse response from: {}'.format(url), cause)


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
        'timeout': 10,
        'delay': 0,
        'workers': os.cpu_count() * 2
    }

    entry = []

    def __init__(self):
        self.request_queue = Queue()
        self.response_queue = Queue()

        self.all_requests = 0
        self.all_responses = 0
        self.failed_urls = []

    def process_before_download(self, req: 'Request') -> Optional['Request']:
        rv = req
        for func in before_download_handlers:
            rv = func(self, rv)
            if not isinstance(rv, Request):
                raise RequestIgnored(req.url)
        return rv

    def process_after_download(self, res: 'Response') -> Optional[Union['Response', 'Request']]:
        rv = res
        for func in after_download_handlers:
            rv = func(self, rv)
            if not isinstance(rv, Response):
                err = ResponseIgnored(res.url)
                if isinstance(rv, Request): err.new_req = rv
                raise err
        return rv

    def process_pipes(self, item: Any, res: 'Response') -> Any:
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

    def download(self):
        while True:
            req = self.request_queue.get()

            try:
                req = self.process_before_download(req)
            except Exception as err:
                if not isinstance(err, RequestIgnored):
                    err = RequestIgnored(req.url, err)
                self.response_queue.put(err)
                continue

            try:
                res = req.send()
            except Exception as err:
                err = DownLoadError(req.url, err)
                err.retry_req = req
                self.response_queue.put(err)
                continue

            try:
                res = self.process_after_download(res)
            except Exception as err:
                if not isinstance(err, ResponseIgnored):
                    err = ResponseIgnored(res.url, err)
                self.response_queue.put(err)
                continue

            self.response_queue.put(res)

    def init_fetchers(self):
        for idx in range(max(self.config['workers'], 1)):
            thread = Thread(target=self.download, name='fetcher-{}'.format(idx))
            thread.daemon = True
            thread.start()

    def init_requests(self) -> None:
        entry = self.entry
        if isinstance(entry, str):
            entry = [entry]
        for req in entry:
            if not isinstance(req, Request):
                req = Request(req)
            self.add_request(req)

    def add_request(self, req: 'Request') -> None:
        self.all_requests += 1
        self.request_queue.put(req)

    def start(self):
        start = time.time()
        logger.info('Spider is running...')
        default_parser = getattr(self, 'parse')

        self.init_requests()
        self.init_fetchers()

        while not self.completed:
            res = self.response_queue.get()
            self.all_responses += 1

            if not self.ensure_valid_response(res):
                continue

            # TODO: add the url to a bloom filter
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
                        self.add_request(item)
                    else:
                        self.process_pipes(item, res)
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

        logger.info('Spider exited; running time: {:.1f}s.'.format(time.time() - start))
        self.log_failed_urls()

    def ensure_valid_response(self, res: Union[SpiderError, requests.Response]) -> bool:
        if isinstance(res, requests.Response):
            return True

        if isinstance(res, RequestIgnored):
            pass
        elif isinstance(res, DownLoadError):
            req = res.retry_req
            if req.retry > 0:
                req.retry -= 1
                # TODO: a retry delay?
                self.add_request(req)
            else:
                self.failed_urls.append(req.url)
        elif isinstance(res, ResponseIgnored):
            if res.new_req:
                self.add_request(res.new_req)

        try:
            self.handle_error(res)
        except Exception as err:
            logger.error('Error in error handler!', exc_info=err)

        return False

    def log_failed_urls(self):
        urls = self.failed_urls
        if not urls: return

        num = len(urls)
        s = 's' if num > 1 else ''
        msg = 'Cannot download from {} url{}:\n{}'.format(num, s, '\n'.join(urls))
        logger.info(msg)

    @property
    def completed(self) -> bool:
        return self.all_requests == self.all_responses

    def parse(self, res: 'Response') -> Generator:
        yield res

    def collect(self, item: Any) -> Any:
        logger.info(item)

    def handle_error(self, reason: SpiderError) -> None:
        logger.error(reason.msg, exc_info=reason.cause)


class Request:
    def __init__(self,
                 url: str,
                 method: str = 'GET',
                 callback: Optional[Callable] = None,
                 state: Optional[dict] = None,
                 session: Union[bool, dict, requests.Session] = False,
                 retry: int = 0,
                 **kw):
        self.url = url
        self.method = method
        self.callback = callback
        self.state = state or {}
        self.session = session
        self.retry = retry
        self.args = kw

    def make_session(self) -> Optional[requests.Session]:
        session = self.session
        if session is True:
            return requests.Session()
        elif isinstance(session, requests.Session):
            return session
        elif isinstance(session, dict):
            sess = requests.Session()
            for key, value in session.items():
                setattr(sess, key, value)
            return sess
        else:
            return None

    def send(self) -> 'Response':
        it = requests
        sess = self.make_session()
        if sess: it = sess

        res = it.request(self.method, self.url, **self.args)
        res.req = self
        res.callback = self.callback
        res.state = self.state
        res.session = sess
        return res

    def __repr__(self):
        return '<Request [{}]>'.format(self.method)


class Response(requests.Response):
    def __init__(self):
        super().__init__()
        self.req: Optional[Request] = None
        self.callback: Optional[Callable] = None
        self.state: dict = {}
        self.session: Optional[requests.Session] = None

    def select(self, selector: str, **kw) -> List[bs4.element.Tag]:
        soup = BeautifulSoup(self.text, 'html.parser')
        return soup.select(selector, **kw)
