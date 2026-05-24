
# from collections import namedtuple
from dataclasses import dataclass
from typing import Any




# RequestToSentry = namedtuple("RequestToSentry", [
#     'ip',
#     'request_path',
#     'headers',
#     'cookies',
#     'time_now',
# ])

@dataclass(frozen=True)
class RequestToSentry:
    ip: Any
    request_path: Any
    headers: Any
    cookies: Any
    time_now: Any

@dataclass(frozen=True)
class ContextForSentry:
    redis: Any
