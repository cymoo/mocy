from typing import Optional, List

import bs4
import requests
from bs4 import BeautifulSoup

from .request import Request


try:
    import lxml
    parser = 'lxml'
except ModuleNotFoundError:
    parser = 'html.parser'


class Response(requests.Response):
    """This object contains a server’s response to an HTTP request."""
    def __init__(self):
        super().__init__()
        self.req: Optional[Request] = None
        self.state: Optional[dict] = None
        self.session: Optional[requests.Session] = None

    def select(self, selector: str, **kw) -> List[bs4.element.Tag]:
        """Perform a CSS selection operation on the HTML element."""
        soup = BeautifulSoup(self.text, parser)
        return soup.select(selector, **kw)
