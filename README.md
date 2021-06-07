# Mocy

## Overview

Mocy is a simple web crawling framework that is flexible and easy to use.

* Concurrent downloads

* Decorators like `@before_download`, `@after_download`, `@pipe`

* Rate limit and retry mechanism

* Session keeping

* More...

## Installation

```bash
$ pip install mocy
```

## A Quick Example

The following is a simple spider to extract upcoming Python events.

```python3
from mocy import Spider, Request, pipe


class SimpleSpider(Spider):
    entry = 'https://www.python.org/'

    def parse(self, res):
        for link in res.select('.event-widget li a'):
            yield Request(
                link['href'],
                state={'name': link.text},
                callback=self.parse_detail_page
            )

    def parse_detail_page(self, res):
        date = ' '.join(res.select('.single-event-date')[0].stripped_strings)
        yield res.state['name'], date

    @pipe
    def output(self, item):
        print(f'{item[0]} will be held on "{item[1]}"')


SimpleSpider().start()
```

The Result is:

```
[2021-06-08 00:59:22] INFO   : Spider is running...
[2021-06-08 00:59:23] INFO   : "GET https://www.python.org/" 200 0.27s
[2021-06-08 00:59:23] INFO   : "GET https://www.python.org/events/python-events/1094/" 200 0.61s
[2021-06-08 00:59:23] INFO   : "GET https://www.python.org/events/python-events/964/" 200 0.63s
[2021-06-08 00:59:23] INFO   : "GET https://www.python.org/events/python-events/1036/" 200 0.69s
[2021-06-08 00:59:23] INFO   : "GET https://www.python.org/events/python-events/1085/" 200 0.69s
[2021-06-08 00:59:24] INFO   : "GET https://www.python.org/events/python-events/833/" 200 0.79s
[2021-06-08 00:59:24] INFO   : Spider exited; total running time 1.12s.

PyFest will be held on "From 16 June through 18 June, 2021"
EuroPython 2021 will be held on "From 26 July through 01 Aug., 2021"
PyCon Namibia 2021 will be held on "From 18 June through 19 June, 2021"
PyOhio 2021 will be held on "31 July, 2021"
SciPy 2021 will be held on "From 12 July through 18 July, 2021"
```

There are some detailed examples in the directory /examples.

## Tests

```bash
$ pytest
```

## License

MIT