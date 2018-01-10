import threading
from functools import wraps
def Category():
    return threading.RLock()
def synchronized(lock = None):
    if not lock: lock = threading.RLock()
    def _dec(f):
        @wraps(f)
        def _f(*args, **kwargs):
            with lock:
                return f(*args, **kwargs)
        return _f
    return _dec
