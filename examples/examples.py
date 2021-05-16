from mocy import Spider, pipe, Request, logger
from pprint import pprint


class ExampleSpider(Spider):
    def entry(self):
        yield Request(
            'http://qr.sjtup.com/admin/login',
            method='POST',
            session=True,
            data={'nickname': 'sjtup', 'password': 'xxx'},
            callback=self.login,
        )
        # yield 'http://httpbin.org/status/404',

    def login(self, res):
        yield Request('/admin/list', callback=self.parse_list)
        yield Request('/admin/edit', callback=self.parse_list)

    def parse_list(self, res):
        for item in res.select('td:first-child a'):
            yield item.text, item['href']

    # @pipe
    # def output(self, result):
    #     (result)


if __name__ == '__main__':
    spider = ExampleSpider()
    spider.start()