import bs4
import logger
import os
import requests
import time
from functools import partial
from queue import Queue
# from threading import Lock
from threading import Thread
from typing import Optional, Callable, Generator, Any, Union, List
from bs4 import BeautifulSoup


before_download_handlers = []
after_download_handlers = []
pipes = []
error_handlers = []


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
        self.all_downloaded = 0
        # self._lock = Lock()

    def process_before_download(self, req: 'Request') -> Optional['Request']:
        rv = req
        for func in before_download_handlers:
            rv = func(self, rv)
            if not isinstance(rv, Request):
                self.all_requests -= 1
                return None
        return rv

    def process_after_download(self, res: 'Response') -> Optional['Response']:
        rv = res
        for func in after_download_handlers:
            rv = func(self, rv)
            if not isinstance(rv, requests.Response):
                return None
        return rv

    def process_pipes(self, item: Any, res: 'Response') -> Any:
        rv = item
        for func in pipes:
            rv = func(self, rv, res)
            if rv is None:
                return None
        return rv

    def download(self):
        while True:
            req = self.request_queue.get()
            # TODO: handle exception
            try:
                res = req.send()
                self.response_queue.put(res)
            except Exception as err:
                # logger.error('cannot download from {}'.format(req.url), exc_info=err)
                err.url = req.url
                self.response_queue.put(err)
            # finally:
            #     with self._lock: self.all_downloaded += 1

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
        logger.info('spider is running...')
        default_parser = getattr(self, 'parse', None)
        default_collector = getattr(self, 'collect', None)

        self.init_requests()
        self.init_fetchers()

        while not self.completed:
            res = self.response_queue.get()
            self.all_downloaded += 1
            if isinstance(res, Exception):
                logger.error('cannot download from {}'.format(res.url), exc_info=res)
                continue
            # res.css = partial(Response.css, res)
            parser = res.callback if res.callback else default_parser

            session = res.session
            close_session = True

            # TODO: handle exception when parsing
            for item in parser(res):
                if isinstance(item, Request):
                    if session and item.session is False:
                        close_session = False
                        item.session = res.session
                    self.add_request(item)
                else:
                    # TODO: handle exception when collecting
                    default_collector(item)

            if session and close_session:
                try:
                    session.close()
                except Exception as err:
                    logger.error('cannot close session', exc_info=err)
        logger.info('spider exited; total running time: {:.1f}s'.format(time.time() - start))

    @property
    def completed(self) -> bool:
        return self.all_requests == self.all_downloaded

    def parse(self, res: 'Response') -> Generator:
        yield res

    def collect(self, result: Any) -> Any:
        pass


class Request:
    def __init__(self,
                 url: str,
                 method: str = 'GET',
                 callback: Optional[Callable] = None,
                 state: Optional[dict] = None,
                 session: Union[bool, dict, requests.Session] = False,
                 **kw):
        self.url = url
        self.method = method
        self.callback = callback
        self.state = state or {}
        self.session = session
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

        # TODO: handle exception
        res = it.request(self.method, self.url, **self.args)
        res.req = self
        res.callback = self.callback
        res.state = self.state
        res.session = sess
        return res

    def __repr__(self):
        return '<Request [{}]>'.format(self.method)


class Response(requests.models.Response):
    def __init__(self):
        super().__init__()
        self.req: Optional[Request] = None
        self.callback: Optional[Callable] = None
        self.state: dict = {}
        self.session: Optional[requests.Session] = None

    def select(self, selector: str, **kw) -> List[bs4.element.Tag]:
        soup = BeautifulSoup(self.text, 'html.parser')
        return soup.select(selector, **kw)

    def css(self, selector: str, **kw):
        pass


class FirstSpider(Spider):
    entry = [
        # 'https://daydream.site/how-to-build-a-web-server/',
        # 'https://bing.com',
        # 'https://baidu.com',
        # 'http://www.sjtup.com',
        'https://foo.com',
    ]

    def parse(self, res: Response) -> Generator:
        yield res.text
        # yield Request('https://daydream.site/how-to-build-a-web-framework/', callback=self.parse_next)
        # yield res.url
        # yield 'yes, it works'

    def parse_next(self, res: Response) -> Generator:
        yield res.text

    def collect(self, result: Any) -> None:
        print(result)
        print('*' * 30)


my_spider = FirstSpider()
my_spider.start()
