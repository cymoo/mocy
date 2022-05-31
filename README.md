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

## API

### Request

```python
class Request(url: str,
              method: str = 'GET',
              
              callback: Optional[Callable] = None,
              session: Union[bool, dict] = False,
              state: Optional[dict] = None,
              
              headers: Optional[dict] = None,
              cookies: Optional[dict] = None,
              params: Optional[dict] = None,
              data: Optional[dict] = None,
              json: Optional[dict] = None,
              files: Optional[dict] = None,
              proxies: Optional[dict] = None,
              verify: bool = True,
              timeout: Optional[Union[Tuple[Number, Number], Number]] = None,
              **kwargs)
```

The popular HTTP library [requests](https://requests.readthedocs.io/en/latest/) is used under the hood. Please refer to its documentation: [requests.request](https://requests.readthedocs.io/en/latest/api/#main-interface). 

It accepts some extra parameters:

**Parameters**:

* callback: It will be used to handle response to this request. The default value is `self.parse`. 
* session: It provides cookie persistence, connection-pooling, and configuration. It can be a `Bool` or `dict`. The default value is `False`, that means no new  [requests.Session](https://requests.readthedocs.io/en/master/user/advanced/#session-objects) will be created.
  * If set to `True`, a [requests.Session](https://requests.readthedocs.io/en/master/user/advanced/#session-objects) object is created, and subsequent requests will be sent under the same session.
  * if set to a `dict`, in addition to the above, the value can be used to provide default data to the `Request`. For example: `session={'auth': ('user', 'pass'), 'headers': {'x-test': 'true'}}`.
* state: It is shared between a request and the corresponding response.



### Response

This object contains a server’s response to an HTTP request. Actually it is the same object as [requests.Response](https://requests.readthedocs.io/en/latest/api/#requests.Response).

Several attributes and methods are attached to this object:

**Attributes**:

* req: The `Request` object.
* state: The same object that was passed by a `Request`.

**Methods**:

* `select(self, selector: str, **kw) -> List[bs4.element.Tag]`

  Perform a CSS selection operation on the HTML element. The powerful HTML parser [Beautiful Soup](https://beautifulsoup.readthedocs.io/) is used. 



### Spider

Base class for spiders. All spiders must inherit from this class.

**Class attributes**:

* WORKERS

  Default: ``os.cpu_count() * 2``

  The number of concurrent requests that will be performed by the downloader. 

* TIMEOUT:

  Default: `30`

  The amount of time (in secs) that the downloader will wait before timeout.

* DOWNLOAD_DELAY

  Default: `0`

  The amount of time (in secs) that the downloader should wait before download.

* RANDOM_DOWNLOAD_DELAY

  Default: `True`

  If enabled, the downloader will wait a random time (0.5 * delay ~ 1.5 * delay by default) before downloading the next page.

* RETRY_TIMES

  Default: `3`

  Maximum number of times to retry when encountering connection issues or unexpected status codes.

* RETRY_CODES:

  Default: `(500, 502, 503, 504, 408, 429)`

  HTTP response status codes to retry. Other errors (DNS or connection issues) are always retried.

  502: Bad Gateway, 503: Service Unavailable, 504: Gateway Timeout, 408: Request Timeout, 429: Too Many Requests.

* RETRY_DELAY

  Default: `1`

  The amount of time (in secs) that the downloader will wait before retrying a failed request.

* DEFAULT_HEADERS

  Default: `{'User-Agent': 'mocy/0.1'}`

**Attributes**：

* `entry: Union[str, Request, Iterable[Union[str, Request]], Callable] = []`

**Methods**:

* `entry() -> Union[str, Request, Iterable[Union[str, Request]], Callable] = []`

* `on_start(self) -> None`

  Called when the spider starts up.

* `on_finish(self) -> None`

  Called when the spider exits.

* `on_error(self, reason: SpiderError) -> None`

  Called when the spider encounters an error when downloading or parsing. It may be called multiple times.

* `parse(self, res: Response) -> Any`

  Parse a response and generate some data or new requests.

* `collect(self, item: Any) -> Any`

  Called when the spider outputs a result. Usually it will be called multiple times.

* `collect(self, item: Any, res: Response) -> Any`

  Called when the spider outputs a result. Usually it will be called multiple times.

* `start(self) -> None`

  Starts up the spider. It will keep running until all requests were processed.



### Decorators

The decorators can be applied to multiple methods of the `Spider` class. They are called in the same order as they were defined.

* `before_download`

  The decorated method is used to modify request objects. If it does not return the same or a new `Request` object, the passed request will be ignored.

* `after_download`

  The decorated method is used to modify response objects. If it does not return the same or a new `Response` object, the passed response will be ignored. If it returns a `Request` object, then the object will be added to the request queue.

* `pipe`

  The decorated method is used to process yielded items. If it returns `None`, the item won't be passed to the next pipeline. `Spider.collect` is a default pipe.



### Exceptions

* `class SpiderError(msg: str, cause: Optional[Exception] = None)`

  Base Class for spider errors. The following exceptions inherit from this class.

  **Attributes**:

  * msg: a brief text that explains what happened.
  * cause: the underlying exception that raised this error.
  * req: the `Request` object.
  * res: the `Response` object; it may be `None`.

* `class RequestIgnored(url: str, cause: Optional[Exception] = None)`

  Indicates a decision was made not to process a request.

* `class ResponseIgnored(url: str, cause: Optional[Exception] = None)`

  Indicates a decision was made not to process a response.

* `class DownLoadError(url: str, cause: Optional[Exception] = None)`

  Indicates an error when downloading.

* `class ParseError(url: str, cause: Optional[Exception] = None)`

  Indicates an error when parsing.



## Tests

```bash
$ pytest
```

## License

MIT