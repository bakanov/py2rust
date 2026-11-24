from enum import Enum

API_VERSION: int = 1


class Status(Enum):
    OK = "ok"
    ERROR = "error"
