import logging

from mocy import Spider, before_download, after_download, pipe, Request
from mocy.exceptions import (
    RequestIgnored,
    ResponseIgnored,
    ParseError,
)


class TestRequestIgnoredError:
    def test_return_none(self):
        error = None

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @before_download
            def return_none(self, request):
                pass

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()

        assert error is None

    def test_return_arbitrary_value(self):
        error = None

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @before_download
            def return_arbitrary_value(self, request):
                return 42

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()

        assert error is None

    def test_raise_error(self):
        exc = ValueError('wrong value')
        error = None

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @before_download
            def raise_error(self, request):
                raise exc

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()

        assert isinstance(error, RequestIgnored)
        assert error.req is not None
        assert error.res is None
        assert error.cause is exc

    def test_return_request(self):
        error = None

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @before_download
            def return_request(self, request):
                return request

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()

        assert error is None


class TestResponseIgnoredError:
    def test_return_none(self):
        error = None

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @after_download
            def return_none(self, response):
                pass

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()

        assert error is None

    def test_return_arbitrary_value(self):
        error = None

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @after_download
            def return_arbitrary(self, response):
                return 42

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()

        assert error is None

    def test_return_request(self):
        error = None
        new_req = Request('https://www.bing.com')

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @after_download
            def return_request(self, response):
                if 'daydream' in response.url:
                    return new_req
                else:
                    return response

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()

        assert error is None

    def test_return_response(self):
        error = None

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @after_download
            def return_response(self, response):
                return response

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()

        assert error is None

    def test_raise_error(self):
        error = None
        exc = ValueError('num 42')

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @after_download
            def return_response(self, response):
                raise exc

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()

        assert isinstance(error, ResponseIgnored)
        assert error.new_req is None
        assert error.req is not None
        assert error.res is not None
        assert error.cause is exc


class TestDownloadError:
    def test_download_error(self):
        class MySpider(Spider):
            entry = ''


class TestParseError:
    def test_default_parse_function(self):
        error = None

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            def parse(self, res):
                1 / 0

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()
        assert isinstance(error, ParseError)
        assert error.req is not None
        assert error.res is not None
        assert isinstance(error.cause, ZeroDivisionError)

    def test_parse_function(self):
        error = None

        class MySpider(Spider):
            @property
            def entry(self):
                return Request('https://daydream.site', callback=self.my_parse_func)

            def my_parse_func(self, res):
                1 / 0

            def on_error(self, reason):
                nonlocal error
                error = reason

        spider = MySpider()
        spider.start()
        assert isinstance(error, ParseError)
        assert error.req is not None
        assert error.res is not None
        assert isinstance(error.cause, ZeroDivisionError)


class TestPipeError:
    def test_raise_error_in_pipe(self, caplog):
        from mocy import logger
        logger.set_level(logging.ERROR)

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @pipe
            def raise_error(self, result):
                raise ValueError('num 42')

        spider = MySpider()
        spider.start()
        record = caplog.records[0]
        assert 'Error when collecting results' in record.message


class TestErrorInErrorHandler:
    def test_raise_error_in_error_handler(self, caplog):
        from mocy import logger
        logger.set_level(logging.ERROR)

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @before_download
            def return_none(self, request):
                raise ValueError('42')

            def on_error(self, reason):
                raise reason

        spider = MySpider()
        spider.start()
        record = caplog.records[0]
        assert 'Error in error handler' in record.message
