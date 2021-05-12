from typing import Optional, Union, Callable

import requests


class Request:
    # TODO: ...
    def __init__(self,
                 url: str,
                 method: str = 'GET',
                 callback: Optional[Callable] = None,
                 state: Optional[dict] = None,
                 session: Union[bool, dict, requests.Session] = False,
                 retry: int = 0,
                 headers: Optional[dict] = None,
                 **kw):
        self.url = url
        self.method = method
        self.callback = callback
        self.state = state or {}
        self.session = session
        self.retry = retry

        self.headers = headers or {}

        self.args = kw

    def _make_session(self) -> Optional[requests.Session]:
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

    @property
    def initial(self):
        """Whether it is a unique request or the first request in a session."""
        return not isinstance(self.session, requests.Session)

    def send(self) -> 'Response':
        it = requests
        sess = self._make_session()
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
