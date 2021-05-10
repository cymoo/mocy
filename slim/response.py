from typing import Optional, Callable, List

import bs4
import requests
from bs4 import BeautifulSoup

from .request import Request


class Response(requests.Response):
    def __init__(self):
        super().__init__()
        self.req: Optional[Request] = None
        self.callback: Optional[Callable] = None
        self.state: dict = {}
        self.session: Optional[requests.Session] = None

    def select(self, selector: str, **kw) -> List[bs4.element.Tag]:
        soup = BeautifulSoup(self.text, 'html.parser')
        return soup.select(selector, **kw)
