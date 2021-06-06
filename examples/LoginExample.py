from mocy import Spider, Request, Response, logger


class ExampleSpider(Spider):
    def entry(self):
        yield Request(
            'https://page-that-needs-login.com',
            method='POST',
            session=True,
            data={'name': 'foo', 'password': 'bar'},
            callback=self.login,
        )

    def login(self, res: Response):
        if res.status_code == 200:
            yield Request('/page-after-login-successfully')
        else:
            logger.warn('login failed')

    def parse(self, res):
        for item in res.select('some-css-selector'):
            yield item.text
