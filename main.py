import os
import time
from functools import partial
from queue import Queue
from threading import Thread
from typing import Optional, Callable, Generator, Any, Union, List

import bs4
import requests
from bs4 import BeautifulSoup


class Spider:
    config = {
        'timeout': 10,
        'delay': 1,
        'workers': os.cpu_count() * 2
    }

    urls = []

    before_download_handlers = []
    after_download_handlers = []
    before_parse_handlers = []
    after_parse_handlers = []
    pipes = []

    def __init__(self):
        self.request_queue = Queue()
        self.response_queue = Queue()

    def parse(self, res: 'Response') -> Generator:
        pass

    def collect(self, result: Any) -> None:
        pass

    def download(self):
        while True:
            req = self.request_queue.get()
            res = requests.request(
                method=req.method,
                url=req.url,
                headers=req.headers
            )
            res.state = req.state
            res.req = req
            self.response_queue.put(res)

    def make_download_threads(self):
        for i in range(4):
            thread = Thread(target=self.download, name='download-thead-{}'.format(i))
            thread.daemon = True
            thread.start()

    def start(self):
        for url in self.urls:
            self.request_queue.put(Request(url))

        self.make_download_threads()

        while True:
            res = self.response_queue.get()
            res.select = partial(Response.select, res)
            if res.req.callback:
                parse_fn = res.req.callback
            else:
                parse_fn = self.parse
            for item in parse_fn(res):
                if isinstance(item, Request):
                    self.request_queue.put(item)
                else:
                    self.collect(item)

    @property
    def completed(self) -> bool:
        if not self.response_queue.empty():
            return False

        for _ in range(5):
            time.sleep(1)
            if not self.response_queue.empty():
                return False

        return True

    def stop(self):
        pass


class Request:
    def __init__(self,
                 url: str,
                 method: str = 'GET',
                 callback: Optional[Callable] = None,
                 headers: Optional[dict] = None,
                 state: Optional[dict] = None):
        self.url = url
        self.callback = callback
        self.method = method
        self.headers = headers
        self.state = state or {}


class Response(requests.models.Response):
    def save(self) -> None:
        pass

    def select(self, selector: str, **kw) -> Union[List[bs4.element.Tag], bs4.element.Tag]:
        soup = BeautifulSoup(self.text, 'html.parser')
        rv = soup.select(selector, **kw)

        return rv[0] if len(rv) == 1 else rv


class FirstSpider(Spider):
    urls = ['https://daydream.site/how-to-build-a-web-server/']

    def parse(self, res: Response) -> Generator:
        yield Request('https://daydream.site/how-to-build-a-web-framework/', callback=self.parse_next)
        yield res.url
        yield 'yes, it works'

    def parse_next(self, res: Response) -> Generator:
        yield res
        yield 'done'

    def collect(self, result: Any) -> None:
        print(result)


spider = FirstSpider()
spider.start()
