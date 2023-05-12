import logging
import os
import time


logging.basicConfig(
    format='%(asctime)s %(levelname)s: %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)


def stop_from_file(path):
    if os.path.exists(path):
        os.remove(path)
        return False
    else:
        return True


def retry(max_tries=2, wait_for=2, on_error=None):
    def decorator(function):
        def wrapped(*args, **kwargs):
            n = max_tries
            while True:
                try:
                    return function(*args, **kwargs)
                except Exception as exc:
                    if on_error is not None:
                        on_error(exc)
                    n -= 1
                    if n == 0:
                        return exc
                    else:
                        time.sleep(wait_for)
        return wrapped
    return decorator
