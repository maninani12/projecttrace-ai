import time

from app.workers.runner import cleanup

if __name__ == "__main__":
    while True:
        cleanup()
        time.sleep(60)
