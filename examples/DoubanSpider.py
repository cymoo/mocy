import re
from mocy import Spider, Request, before_download
from mocy.utils import random_ip


class DoubanSpider(Spider):
    entry = 'https://book.douban.com/tag/历史?start=0&type=T'

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

    def on_start(self) -> None:
        self.books = []

    def collect(self, item):
        self.books.append(item)

    def on_finish(self):
        self.books.sort(key=lambda x: x[1], reverse=True)
        for book in self.books:
            print(f'{book[1]} --- {book[0]}')


if __name__ == '__main__':
    DoubanSpider().start()
