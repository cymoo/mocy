import pytest
from mocy import Spider, before_download, after_download


class TestSpider(Spider):
    entry = 'https://daydream.site/'

    def parse(self, res):
        return res


def before_download_handler_add_header(spider, request):
    request.headers['foo'] = 'bar'
    return request


def before_download_handler_change_header(spider, request):
    request.headers['foo'] = request.headers['foo'] + ' bar'
    return request


def before_download_handler_return_none(spider, request):
    request.headers['bar'] = 13


def before_download_handler_raise_exception(spider, request):
    raise ValueError('test raise an exception')


class TestBeforeDownloadHandler:
    def test_add_header(self):
        TestSpider.before_download_handlers = [before_download_handler_add_header]
        TestSpider().start()


if __name__ == '__main__':
    pytest.main()
