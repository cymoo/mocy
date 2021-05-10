from slim import Spider, pipe


class ExampleSpider(Spider):
    entry = 'http://www.sjtup.com'

    def parse(self, res):
        for item in res.select('.news-body h3'):
            yield item.text

    @pipe
    def output(self, result):
        print(result)


spider = ExampleSpider()
spider.start()
