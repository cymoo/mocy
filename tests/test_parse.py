from mocy import Spider, Request


class TestEntry:
    def test_entry(self):
        entries = [
            'https://daydream.site',
            Request('https://daydream.site'),
            lambda x: 'https://daydream.site',
            lambda x: Request('https://daydream.site'),
            lambda x: ['https://daydream.site'],
        ]

        class MySpider(Spider):
            def parse(self, res):
                yield res.req.url

        for entry in entries:
            MySpider.entry = entry
            spider = MySpider()
            assert next(iter(spider))[0] == 'https://daydream.site'


class TestParse:
    def test_return_iterable(self):
        class MySpider(Spider):
            entry = 'https://daydream.site/'

            def parse(self, res):
                return [1, 2]

        spider = MySpider()
        assert list(map(lambda x: x[0], iter(spider))) == [1, 2]

    def test_parse_func_is_generator(self):
        class MySpider(Spider):
            entry = 'https://daydream.site/'

            def parse(self, res):
                yield 1
                yield 2

        spider = MySpider()
        assert list(map(lambda x: x[0], iter(spider))) == [1, 2]

    def test_return_non_iterable(self):
        class MySpider(Spider):
            entry = 'https://daydream.site/'

            def parse(self, res):
                yield 42
                yield Request('https://www.baidu.com', callback=self.parse1)

            def parse1(self, res):
                pass

        spider = MySpider()
        assert list(map(lambda x: x[0], iter(spider))) == [42]

    def test_pass_state_between_request_and_response(self):
        state = {'foo': 'bar'}
        state1 = None

        class MySpider(Spider):
            def entry(self):
                return Request('https://daydream.site', state=state)

            def parse(self, res):
                nonlocal state1
                state1 = res.state

        MySpider().start()

        assert state == state1

