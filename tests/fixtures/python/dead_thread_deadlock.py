"""Fixture: a two-thread lock-order deadlock. THIS PROGRAM HANGS FOREVER.

A GPU batch worker locks the model then the tokenizer; a cache refresher locks the tokenizer
then the model. Both are non-daemon threads joined without a timeout, so even Ctrl+C cannot
end the process. Run it only under a watchdog:

    python hang_watchdog.py --dump-after 1 --kill-after 3 dead_thread_deadlock.py
"""

import threading
import time

model_lock = threading.Lock()
tokenizer_lock = threading.Lock()


def gpu_batch_worker():
    with model_lock:
        time.sleep(0.05)
        with tokenizer_lock:
            print("batch embedded")


def cache_refresher():
    with tokenizer_lock:
        time.sleep(0.05)
        with model_lock:
            print("cache refreshed")


def main():
    print("workers started", flush=True)
    threads = [threading.Thread(target=gpu_batch_worker, name="gpu-batch-worker"),
               threading.Thread(target=cache_refresher, name="cache-refresher")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
