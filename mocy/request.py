from numbers import Number
from typing import Optional, Union, Callable, Tuple

import requests


class Request:
    def __init__(self,
                 url: str,
                 method: str = 'GET',

                 callback: Optional[Callable] = None,
                 session: Union[bool, dict, requests.Session] = False,
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
                 **kwargs) -> None:
        self.url = url
        self.method = method

        self.callback = callback
        self.session = session
        self.state = state

        self.headers = headers or {}
        self.cookies = cookies
        self.params = params
        self.data = data
        self.json = json
        self.files = files
        self.proxies = proxies
        self.verify = verify
        self.timeout = timeout

        self.kwargs = kwargs

        self.retry_num = 0

    def send(self) -> 'Response':
        """Send a request and return a response."""
        it = requests
        sess = self._get_session()
        if sess:
            it = sess

        res = it.request(self.method, self.url, **self._prepare_args())
        res.req = self
        res.state = self.state
        res.session = sess
        return res

    @property
    def initial(self) -> bool:
        """Whether it is an independent request or the first request in a session."""
        return not isinstance(self.session, requests.Session)

    def _get_session(self) -> Optional[requests.Session]:
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

    def _prepare_args(self) -> dict:
        args = {}

        for name in ('headers', 'cookies', 'params', 'data',
                     'json', 'files', 'proxies', 'verify', 'timeout'):
            value = getattr(self, name)
            if value:
                args[name] = value

        args.update(self.kwargs)
        return args

    def __repr__(self) -> str:
        return '<Request [{}]>'.format(self.method)


from .response import Response
