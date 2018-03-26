#!/usr/bin/env python

import argparse
import asyncio
import logging
import zmq
import zmq.asyncio

from aiosmtpd.controller import Controller
from aiosmtpd.handlers import AsyncMessage


log = logging.getLogger(__name__)


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("--mail-queue-host",
                        help="message queue host",
                        default="*",
                        type=str)

    parser.add_argument("--mail-queue-port",
                        help="message queue port",
                        default=5563,
                        type=int)

    parser.add_argument("--mail-host",
                        help="mail host",
                        default="0.0.0.0",
                        type=str)

    parser.add_argument("--mail-port",
                        help="mail port",
                        default=1025,
                        type=int)

    opts = parser.parse_args()
    return opts


class ZeroMQHandler(AsyncMessage):

    def __init__(self, publisher, debug_queue=None, message_class=None):

        self._publisher = publisher
        self._debug_queue = debug_queue

        super().__init__(message_class)


    async def handle_DATA(self, server, session, envelope):

        log.debug('Receiving message from: {0}'.format(session.peer))
        log.debug('Message addressed from: {0}'.format(envelope.mail_from))
        log.debug('Message addressed to  : {0}'.format(envelope.rcpt_tos))
        log.debug('Message length        : {0}'.format(len(envelope.content)))

        return await super().handle_DATA(server, session, envelope)


    async def handle_message(self, message):

        # message is an email.message.Message object

        log.debug('message = {0}'.format(message.as_bytes()))

        # Use message enveloping pattern so we can filter messages
        # on the client side. This approach has a flaw in that if
        # the message was sent to multiple people, the tos variable
        # will have multiple email addresses in it, any of which could
        # show up at any index in the list. Client side filtering only
        # matches from the beginning of the key. Most of the time,
        # this probably won't be much of a problem because in my
        # use cases, emails sent through the system will probably only
        # be sent to one recipient.

        tos = message['X-RcptTo'].encode()
        msg_bytes = message.as_bytes()
        await self._publisher.send_multipart([tos, msg_bytes])

        if self._debug_queue is not None:
            await self._debug_queue.put(msg_bytes)


class MailQueueServer(object):

    def __init__(self, queue_host, queue_port, mail_host, mail_port):

        # message queue variables
        self._queue_host = queue_host
        self._queue_port = queue_port
        self.context = None
        self.publisher = None

        # mail server variables
        self._mail_host = mail_host
        self._mail_port = mail_port
        self.handler = None
        self.controller = None

        # store emails for debugging
        self._store_emails = False
        self.queue = None



    @property
    def store_emails(self):

        return self._store_emails


    @store_emails.setter
    def store_emails(self, value):

        if type(value) is not bool:
            raise Exception("bad value: should be bool")

        self._store_emails = value


    def start(self):

        # Prepare our message queue context and publisher
        self.context   = zmq.asyncio.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind("tcp://{0}:{1}".format(self._queue_host,self._queue_port))

        # setup the debug queue
        if self.store_emails is True and self.queue is None:
            self.queue = asyncio.Queue()

        # Prepare the mail server handler and controller
        self.handler = ZeroMQHandler(self.publisher, self.queue)
        self.controller = Controller(self.handler,
                hostname=self._mail_host, port=self._mail_port)

        self.controller.start()


    def stop(self):

        # stop/reset the mail server
        self.controller.stop()
        self.controller = None
        self.handler = None

        # tear down the debug queue
        self.queue = None

        # tear down the message queue
        self.publisher.close()
        self.publisher = None
        self.context.term()
        self.context = None


    def __enter__(self):

        logging.debug('Entering context')

        self.start()

        return self


    def __exit__(self, exc_type, exc_value, traceback):

        logging.debug('Exiting context')

        self.stop()


async def amain(opts,loop):

    s = MailQueueServer(opts.mail_queue_host,
                        opts.mail_queue_port,
                        opts.mail_host,
                        opts.mail_port)
    s.start()


if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG)

    opts = parse_arguments()

    loop = asyncio.get_event_loop()
    loop.create_task(amain(opts,loop))

    try: 
        loop.run_forever()
    except KeyboardInterrupt:
        pass
