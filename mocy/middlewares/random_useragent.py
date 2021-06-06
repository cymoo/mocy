import os
import random

dirname = os.path.dirname(os.path.abspath(__file__))

# The useragent list was taken from: https://techblog.willshouse.com/2012/01/03/most-common-user-agents/
with open(os.path.join(dirname, 'useragents.txt'), 'rt') as fp:
    useragents = []
    for line in fp:
        line = line.strip()
        if line: useragents.append(line)


def random_useragent(spider, request):
    if request.initial:
        request.headers['User-Agent'] = random.choice(useragents)
    return request
