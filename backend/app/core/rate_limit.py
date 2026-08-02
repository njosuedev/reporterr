"""Rate limiting via slowapi (in-memory, per-process — fine for single-instance VPS deploy)."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
