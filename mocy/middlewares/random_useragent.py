import random

# The useragent list was taken from: https://techblog.willshouse.com/2012/01/03/most-common-user-agents/
with open('useragents.txt', 'rt') as fp:
    useragents = [line.strip() for line in fp.readlines()]


def random_useragent(spider, request):
    if request.initial:
        request.headers['User-Agent'] = random.choice(useragents)
    return request
