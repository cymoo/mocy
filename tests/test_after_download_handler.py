from contextlib import contextmanager

import requests

from mocy import Spider, after_download
from mocy.exceptions import SpiderError, ResponseIgnored
from mocy.request import Request


class MySpider(Spider):
    entry = 'https://daydream.site/'

    @after_download
    def test_using_decorator(self, response):
        response.foo = '1'
        return response

    @after_download
    def test_using_decorator_sequentially(self, response):
        response.foo = response.foo + '2'
        return response

    def parse(self, response):
        yield response


def check_first_argument(spider, response):
    response.spider = spider
    return response


def return_response(spider, response):
    return response


def return_request(spider, response):
    if 'bing' not in response.url:
        return Request('https://www.bing.com')
    else:
        return response


def return_none(spider, response):
    pass


def return_arbitrary_value(spider, response):
    return 'foo'


def raise_error(spider, response):
    raise ValueError('test raise an exception')


class TestAfterDownloadHandler:
    @contextmanager
    def start(self, handlers=None):
        old_handlers = MySpider.after_download_handlers
        if handlers:
            MySpider.after_download_handlers = handlers
        spider = MySpider()
        item = next(iter(spider))
        if isinstance(item, SpiderError):
            yield item
        else:
            yield item[0]
        MySpider.after_download_handlers = old_handlers

    def test_using_decorator(self):
        with self.start() as item:
            assert isinstance(item, requests.Response)
            assert isinstance(item.req, Request)
            assert item.foo == '12'

    def test_first_argument(self):
        with self.start([check_first_argument]) as item:
            assert isinstance(item.spider, Spider)

    def test_return_request(self):
        old_handlers = MySpider.after_download_handlers
        MySpider.after_download_handlers = [return_request]
        spider = MySpider()
        it = iter(spider)
        item1 = next(it)
        assert isinstance(item1, ResponseIgnored)
        assert isinstance(item1.req, Request)
        assert isinstance(item1.res, requests.Response)
        assert item1.cause is None
        item2 = next(it)
        assert isinstance(item2[0], requests.Response)
        assert item2[0].url == 'https://cn.bing.com/'

        MySpider.after_download_handlers = old_handlers

    def test_return_none(self):
        with self.start([return_none]) as item:
            assert isinstance(item, ResponseIgnored)
            assert isinstance(item.req, Request)
            assert isinstance(item.res, requests.Response)
            assert item.cause is None

    def test_return_arbitrary_value(self):
        with self.start([return_arbitrary_value]) as item:
            assert isinstance(item, ResponseIgnored)
            assert isinstance(item.req, Request)
            assert isinstance(item.res, requests.Response)
            assert item.cause is None

    def test_raise_error(self):
        with self.start([raise_error]) as item:
            assert isinstance(item, ResponseIgnored)
            assert isinstance(item.req, Request)
            assert isinstance(item.res, requests.Response)
            assert isinstance(item.cause, ValueError)
