import logging

import pytest
from mocy import Spider, before_download, after_download, pipe
from mocy.exceptions import (
    SpiderError,
    RequestIgnored,
    ResponseIgnored,
    DownLoadError,
    ParseError,
    PipeError
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

        assert isinstance(error, RequestIgnored)
        assert error.req is not None
        assert error.res is None
        assert error.cause is None

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

        assert isinstance(error, RequestIgnored)
        assert error.req is not None
        assert error.res is None
        assert error.cause is None

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
    pass


class TestDownloadError:
    pass


class TestParseError:
    pass


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
        assert 'Error occurred when collecting results' in record.message


class TestErrorInErrorHandler:
    def test_raise_error_in_error_handler(self, caplog):
        from mocy import logger
        logger.set_level(logging.ERROR)

        class MySpider(Spider):
            entry = 'https://daydream.site/'

            @before_download
            def return_none(self, request):
                pass

            def on_error(self, reason):
                raise reason

        spider = MySpider()
        spider.start()
        record = caplog.records[0]
        assert 'Error in error handler' in record.message

