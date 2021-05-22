from mocy import Spider, pipe, Request, logger, before_download, after_download
from mocy.utils import random_ip
from pprint import pprint
import re


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


class LiaoXueFengSpider(Spider):
    entry = [
        'https://www.liaoxuefeng.com/wiki/1252599548343744/1255876875896416'
    ]

    def parse(self, res):
        for item in res.select('#x-content'):
            print(item.text)
            yield item


class DoubanSpider(Spider):
    entry = 'https://book.douban.com/tag/%E7%BC%96%E7%A8%8B?start=0&type=T'

    def parse(self, res):
        for item in res.select('.subject-item'):
            title = re.sub(r'\s+', ' ', item.select('h2')[0].text.strip())
            rating_el = item.select('.rating_nums')
            rating = rating_el[0].text.strip() if rating_el else ''
            yield title, rating

        next_link = res.select('.paginator .next a')
        if next_link:
            next_url = next_link[0]['href']
            yield Request(next_url)

    @before_download
    def fake_ip(self, req):
        req.headers['X-Forwarded-For'] = random_ip()
        return req

    @before_download
    def peek_header(self, req):
        pprint(req.__dict__)
        return req

    def on_start(self) -> None:
        self.books = []

    def collect(self, item):
        self.books.append(item)

    def on_finish(self):
        self.books.sort(key=lambda x: x[1], reverse=True)
        with open('cs-books.txt', 'wt') as fp:
            for book in self.books:
                fp.write(book[1] + '---' + book[0] + '\n')


if __name__ == '__main__':
    # spider = ExampleSpider()
    # spider.start()
    # spider = LiaoXueFengSpider()
    # spider.start()
    spider = DoubanSpider()
    spider.start()
