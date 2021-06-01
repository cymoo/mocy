from contextlib import contextmanager

import pytest
import requests

from mocy import Spider, before_download
from mocy.exceptions import SpiderError, RequestIgnored
from mocy.request import Request


class MySpider(Spider):
    entry = 'https://daydream.site/'

    @before_download
    def test_using_decorator(self, request):
        request.headers['bar'] = '42'
        return request

    def parse(self, response):
        yield response


def check_first_argument(spider, request):
    request.spider = spider
    return request


def add_header(spider, request):
    request.headers['foo'] = '1'
    return request


def modify_header(spider, request):
    request.headers['foo'] = request.headers['foo'] + '2'
    return request


def return_none(spider, request):
    pass


def return_arbitrary_value(spider, request):
    return 'foo'


def raise_error(spider, request):
    raise ValueError('test raise an exception')


class TestBeforeDownloadHandler:
    @contextmanager
    def start(self, handlers=None):
        old_handlers = MySpider.before_download_handlers
        if handlers:
            MySpider.before_download_handlers = handlers
        spider = MySpider()
        item = next(iter(spider))
        if isinstance(item, SpiderError):
            yield item
        else:
            yield item[0]
        MySpider.before_download_handlers = old_handlers

    def test_using_decorator(self):
        with self.start() as item:
            assert isinstance(item, requests.Response)
            assert isinstance(item.req, Request)
            assert item.req.headers['bar'] == '42'

    def test_first_argument(self):
        with self.start([check_first_argument]) as item:
            assert isinstance(item.req.spider, Spider)

    def test_add_header(self):
        with self.start([add_header]) as item:
            assert isinstance(item, requests.Response)
            assert isinstance(item.req, Request)
            assert item.req.headers['foo'] == '1'

    def test_modify_header(self):
        with self.start([
            add_header,
            modify_header
        ]) as item:
            assert isinstance(item, requests.Response)
            assert isinstance(item.req, Request)
            assert item.req.headers['foo'] == '12'

    def test_return_none(self):
        with self.start([return_none]) as item:
            assert isinstance(item, RequestIgnored)
            assert isinstance(item.req, Request)
            assert item.cause is None

    def test_return_arbitrary_value(self):
        with self.start([return_arbitrary_value]) as item:
            assert isinstance(item, RequestIgnored)
            assert isinstance(item.req, Request)
            assert item.cause is None

    def test_raise_error(self):
        with self.start([raise_error]) as item:
            assert isinstance(item, RequestIgnored)
            assert isinstance(item.req, Request)
            assert isinstance(item.cause, ValueError)


if __name__ == '__main__':
    pytest.main()
