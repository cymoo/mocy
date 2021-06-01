from typing import Optional


class SpiderError(Exception):
    def __init__(self, msg: str, cause: Optional[Exception] = None) -> None:
        self.msg = msg
        self.cause = cause
        self.req = None
        self.res = None


class RequestIgnored(SpiderError):
    def __init__(self, url: str, cause: Optional[Exception] = None) -> None:
        super().__init__('Request was ignored for {}'.format(url), cause)


class ResponseIgnored(SpiderError):
    def __init__(self, url: str, cause: Optional[Exception] = None) -> None:
        self.new_req = None
        super().__init__('Response was ignored for {}'.format(url), cause)


class DownLoadError(SpiderError):
    def __init__(self, url: str, cause: Optional[Exception] = None) -> None:
        self.will_retry = False
        super().__init__('Cannot download from {}'.format(url), cause)


class ParseError(SpiderError):
    def __init__(self, url: str, cause: Optional[Exception] = None) -> None:
        super().__init__('Error occurred when parsing response from {}'.format(url), cause)


class PipeError(SpiderError):
    def __init__(self, url: str, cause: Optional[Exception] = None) -> None:
        super().__init__('Error occurred when collecting results from {}'.format(url), cause)
