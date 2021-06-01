import logging

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


class TestPipes:
    def start(self, do_assert, handlers=None):
        old_handlers = MySpider.pipes
        if handlers:
            MySpider.pipes = handlers
        spider = MySpider()
        for item, res in spider:
            value = spider._start_pipes(item, res)
            if value is not None:
                do_assert(value)
        MySpider.pipes = old_handlers

    def test_using_decorator(self):
        def do_assert(value):
            assert not value.startswith('Web')
            assert value.endswith('1')

        self.start(do_assert)

    def test_raise_error(self, caplog):
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
