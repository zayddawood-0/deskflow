"""slowapi limiter with in-memory storage.

Best-effort by design: counters live in the process memory of whichever instance
handles the request. On Vercel serverless each warm lambda instance keeps its own
counters (no shared store), so the effective limit is per-instance — acceptable
trade-off, documented in docs/AUTH_AND_SECURITY.md and docs/DEPLOYMENT.md.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

LOGIN_RATE_LIMIT = "5/minute"
REGISTER_RATE_LIMIT = "10/minute"
