import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_testing = os.environ.get("TESTING", "false").lower() == "true"
limiter = Limiter(key_func=get_remote_address, enabled=not _testing)
