import contextlib
import threading
from concurrent.futures import Future

_lock = threading.Lock()
_results = None


@contextlib.contextmanager
def processing_run():
    global _results
    _results = {}
    try:
        yield
    finally:
        _results = None


def run_once(key, fn):
    results = _results
    if results is None:
        return fn()
    new = Future()
    with _lock:
        result = results.setdefault(key, new)
    if result is new:
        try:
            result.set_result(fn())
        except BaseException as err:
            result.set_exception(err)
    return result.result()
