from mocy import Spider, Request


class TestDefaultHeaders:
    def test_default_headers(self):
        headers1 = headers2 = None

        class MySpider(Spider):
            DEFAULT_HEADERS = {'foo': 'bar'}
            entry = 'https://daydream.site'

            def parse(self, res):
                nonlocal headers1
                headers1 = res.req.headers
                yield Request('https://www.baidu.com', callback=self.parse1)

            def parse1(self, res):
                nonlocal headers2
                headers2 = res.req.headers

        MySpider().start()
        assert headers1['foo'] == 'bar'
        assert headers2['foo'] == 'bar'


class TestRetry:
    def start(
        self,
        caplog,
        url,
        retry_times=None,
        retry_codes=None,
        timeout=None,
        expected_retry_times=None,
    ):
        class MySpider(Spider):
            TIMEOUT = 1
            entry = url

        if retry_times is not None:
            MySpider.RETRY_TIMES = retry_times
        if retry_codes is not None:
            MySpider.RETRY_CODES = retry_codes
        if timeout is not None:
            MySpider.TIMEOUT = timeout

        MySpider().start()
        count = 0
        for record in caplog.records:
            if 'Retrying' in record.message:
                count += 1

        if expected_retry_times is None:
            assert count == retry_times
        else:
            assert count == expected_retry_times

    def test_retry_times(self, caplog):
        self.start(caplog, 'https://some-url-not-exists', retry_times=2, timeout=1)
        caplog.records.clear()
        self.start(caplog, 'https://some-url-not-exists', retry_times=0, timeout=1)

    def test_retry_status_code(self, caplog):
        self.start(
            caplog,
            'https://daydream.site/path-not-exists',
            retry_times=2,
            retry_codes=[404],
        )
        caplog.records.clear()
        self.start(
            caplog,
            'https://daydream.site/path-not-exists',
            retry_times=5,
            retry_codes=[500],
            expected_retry_times=0,
        )
