from mocy import Spider


class LanguageTrendsSpider(Spider):
    entry = 'https://www.tiobe.com/tiobe-index/'

    def parse(self, res):
        for tr in res.select('#top20 tbody tr'):
            tds = tr.select('td')
            yield tds[3].text, tds[4].text

    def collect(self, item):
        print(item)


if __name__ == '__main__':
    LanguageTrendsSpider().start()
