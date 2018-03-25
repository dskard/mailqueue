
import zmq
import threading
import queue
import logging


log = logging.getLogger(__name__)


class MailQueueClient(object):

    def __init__(self, queue_host="mail-server", queue_port=5563, filter_pattern=""):
        self._context = None
        self._subscriber = None
        self._queue_host = None
        self._queue_port = None
        self._filter_pattern = None
        self._thread = threading.Thread(target=self.store_messages)

        self.queue_host = queue_host
        self.queue_port = queue_port
        self.filter_pattern = filter_pattern

        self.messages = queue.Queue()

        self._stop_event = None

        self._started = False


    @property
    def queue_host(self):
        return self._queue_host


    @queue_host.setter
    def queue_host(self, value):
        self._queue_host = value


    @property
    def queue_port(self):
        return self._queue_port


    @queue_port.setter
    def queue_port(self, value):
        self._queue_port = int(value)


    @property
    def filter_pattern(self):
        return self._filter_pattern


    @filter_pattern.setter
    def filter_pattern(self, value):
        self._filter_pattern = value.encode()


    def store_messages(self):
        """add new messages to the queue, in a separate thread"""

        poller = zmq.Poller()
        poller.register(self._subscriber, zmq.POLLIN)

        while self._stop_event.is_set() is False:

            log.debug("stop event set? {0}".format(self._stop_event.is_set()))
            socks = dict(poller.poll(500))

            if self._subscriber in socks and socks[self._subscriber] == zmq.POLLIN:
                # Read envelope with address
                log.debug("waiting on subscriber to receive message")
                # [rcpttos,data] = self._subscriber.recv_multipart()
                data = self._subscriber.recv()

                log.debug("received message: %s" % (data))
                self.messages.put(data)

                log.debug("Message count: %i" % (self.messages.qsize()))

        log.debug("leaving thread")


    def start(self):
        log.debug("starting subscriber thread")

        # setup the zmq subscriber
        self._context = zmq.Context()
        self._subscriber = self._context.socket(zmq.SUB)
        queue_uri = "tcp://{0}:{1}".format(self._queue_host,self._queue_port)
        log.debug('queue_uri = {0}'.format(queue_uri))
        self._subscriber.connect(queue_uri)
        self._subscriber.setsockopt(zmq.SUBSCRIBE, self._filter_pattern)

        self._stop_event = threading.Event()

        # start the subscriber thread
        self._thread.start()

        self._started = True


    def stop(self):

        if self._started is not True:
            log.debug("skipping stop(): client was never started")
            return

        log.debug("set the thread stop event...")

        self._stop_event.set()

        log.debug("waiting for thread to terminate ...")

        # wait for the thread to terminate
        self._thread.join()

        log.debug("terminating subscriber...")

        # terminate the subscriber
        self._subscriber.close()
        self._subscriber = None

        log.debug("terminating context ...")

        # terminate the context
        self._context.term()
        self._context = None

        log.debug("finished terminating subscriber thread")

        self._started = False
