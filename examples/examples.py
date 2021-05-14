from mocy import Spider, pipe, Request, logger
import scrapy
from pprint import pprint


class ExampleSpider(Spider):
    entry = [Request(
        'http://qr.sjtup.com/admin/login',
        method='POST',
        session=True,
        data={
            'nickname': 'sjtup',
            'password': 'Sjtup313',
        }
    ),
        'http://httpbin.org/status/404',
    ]

    def parse(self, res):
        yield Request('http://qr.sjtup.com/admin/list', callback=self.parse_list)

    def parse_list(self, res):
        for item in res.select('td:first-child a'):
            yield item.text, item['href']

    # @pipe
    # def output(self, result):
    #     (result)


class BlogSpider(scrapy.Spider):
    name = 'blogspider'
    start_urls = ['https://www.zyte.com/blog/']

    def parse(self, response):
        for title in response.css('.oxy-post-title'):
            yield {'title': title.css('::text').get()}

        for next_page in response.css('a.next'):
            yield response.follow(next_page, self.parse)


if __name__ == '__main__':
    spider = ExampleSpider()
    spider.start()

    # from flask import Flask
    #
    # app = Flask(__name__)
    #
    # @app.get('/')
    # def foo():
    #     return 'hello'
    #
    # app.run()

