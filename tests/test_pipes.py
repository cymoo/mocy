import pytest
from contextlib import contextmanager
from mocy import Spider, after_download
from mocy.request import Request
from mocy.exceptions import SpiderError, RequestIgnored, ResponseIgnored
import requests


class MySpider(Spider):
    entry = 'https://daydream.site/'

    def parse(self, response):
        response.encoding = 'utf8'
        for link in response.select('h2 a'):
            yield link.text


if __name__ == '__main__':
    spider = MySpider()
    spider.start()
