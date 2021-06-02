import logging

import requests

from mocy import Spider, pipe


class MySpider(Spider):
    entry = 'https://daydream.site/'

    def parse(self, response):
        response.encoding = 'utf8'
        for link in response.select('h2 a'):
            yield link.text

    @pipe
    def test_using_decorator(self, result):
        if not result.startswith('Web'):
            return result

    @pipe
    def test_using_decorator_sequentially(self, result, response):
        return result + '1'


def return_none(spider, result):
    return None


def return_some(spider, result):
    if not result.startswith('Web'):
        return result


def return_some_and_check_arguments(spider, result, response):
    assert isinstance(response, requests.Response)
    assert isinstance(spider, Spider)
    if not result.startswith('Web'):
        return result


class TestPipes:
    def start(self, func, handlers=None):
        old_handlers = MySpider.pipes
        if handlers:
            MySpider.pipes = handlers
        spider = MySpider()
        for item, res in spider:
            value = spider._start_pipes(item, res)
            if value is not None:
                func(value)
        MySpider.pipes = old_handlers

    def test_using_decorator(self):
        def do_assert(value):
            assert not value.startswith('Web')
            assert value.endswith('1')

        self.start(do_assert)

    def test_return_none(self):
        def cb(value):
            raise Exception('cannot be here')

        self.start(cb, [return_none, return_some])

    def test_return_some(self):
        def do_assert(value):
            assert not value.startswith('Web')

        self.start(do_assert, [return_some])
        self.start(do_assert, [return_some_and_check_arguments])
