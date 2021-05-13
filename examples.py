from mocy import Spider, pipe, Request, logger
from pprint import pprint


class ExampleSpider(Spider):
    entry = Request(
        'http://qr.sjtup.com/admin/login',
        method='POST',
        session=True,
        data={
            'nickname': 'xxx',
            'password': 'xxx',
        }
    )

    def parse(self, res):
        yield Request('http://qr.sjtup.com/admin/list', callback=self.parse_list)

    def parse_list(self, res):
        for item in res.select('td:first-child a'):
            yield item.text, item['href']

    # @pipe
    # def output(self, result):
    #     (result)


spider = ExampleSpider()
spider.start()
