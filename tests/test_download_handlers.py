import pytest
from mocy import Spider, before_download
from mocy.request import Request
from mocy.exceptions import SpiderError, RequestIgnored, ResponseIgnored
import requests


class MySpider(Spider):
    entry = 'https://daydream.site/'

    @before_download
    def add_header(self, req):
        req.headers['bar'] = '42'
        return req

    def parse(self, res):
        yield res


def before_download_handler_add_header(spider, request):
    request.headers['foo'] = 'bar'
    return request


def before_download_handler_change_header(spider, request):
    request.headers['foo'] = request.headers['foo'] + '1'
    return request


def before_download_handler_return_none(spider, request):
    request.headers['bar'] = 13


def before_download_handler_raise_error(spider, request):
    raise ValueError('test raise an exception')


class TestBeforeDownloadHandler:
    def test_using_decorator(self):
        spider = MySpider()
        item = next(iter(spider))
        if not isinstance(item, SpiderError):
            result, _ = item
            assert result.req.headers['bar'] == '42'

    def test_add_header(self):
        MySpider.before_download_handlers = [before_download_handler_add_header]
        spider = MySpider()
        item = next(iter(spider))
        if not isinstance(item, SpiderError):
            result, _ = item
            assert isinstance(result, requests.Response)
            assert isinstance(result.req, Request)
            assert result.req.headers['foo'] == 'bar'

    def test_modify_header(self):
        MySpider.before_download_handlers = [
            before_download_handler_add_header,
            before_download_handler_change_header
        ]
        spider = MySpider()
        item = next(iter(spider))
        if not isinstance(item, SpiderError):
            result, _ = item
            assert isinstance(result, requests.Response)
            assert isinstance(result.req, Request)
            assert result.req.headers['foo'] == 'bar1'

    def test_return_none(self):
        MySpider.before_download_handlers = [before_download_handler_return_none]
        spider = MySpider()
        item = next(iter(spider))
        assert isinstance(item, RequestIgnored)
        assert isinstance(item.req, Request)
        assert item.cause is None

    def test_raise_error(self):
        MySpider.before_download_handlers = [before_download_handler_raise_error]
        spider = MySpider()
        item = next(iter(spider))
        assert isinstance(item, RequestIgnored)
        assert isinstance(item.req, Request)
        assert isinstance(item.cause, ValueError)


if __name__ == '__main__':
    pytest.main()
