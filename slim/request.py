from typing import Optional, Union, Callable

import requests


class Request:
    def __init__(self,
                 url: str,
                 method: str = 'GET',
                 callback: Optional[Callable] = None,
                 state: Optional[dict] = None,
                 session: Union[bool, dict, requests.Session] = False,
                 retry: int = 0,
                 **kw):
        self.url = url
        self.method = method
        self.callback = callback
        self.state = state or {}
        self.session = session
        self.retry = retry
        self.args = kw

    def make_session(self) -> Optional[requests.Session]:
        session = self.session
        if session is True:
            return requests.Session()
        elif isinstance(session, requests.Session):
            return session
        elif isinstance(session, dict):
            sess = requests.Session()
            for key, value in session.items():
                setattr(sess, key, value)
            return sess
        else:
            return None

    def send(self) -> 'Response':
        it = requests
        sess = self.make_session()
        if sess: it = sess

        res = it.request(self.method, self.url, **self.args)
        res.req = self
        res.callback = self.callback
        res.state = self.state
        res.session = sess
        return res

    def __repr__(self):
        return '<Request [{}]>'.format(self.method)


from .response import Response
