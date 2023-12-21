import logging
import threading

def worker(event, delay):
    while not event.isSet():
        print("worker {} thread checking in".format(delay))
        event.wait(delay)

def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(relativeCreated)6d %(threadName)s %(message)s"
    )
    event = threading.Event()

    thread = threading.Thread(target=worker, args=(event,1))
    thread_two = threading.Thread(target=worker, args=(event,3))
    thread.start()
    thread_two.start()

    while not event.isSet():
        try:
            print("Checking in from main thread")
            event.wait(0.75)
        except KeyboardInterrupt:
            event.set()
            break

if __name__ == "__main__":
    main()