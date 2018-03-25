import logging
import pytest

from mqserver import MailQueueServer
from mqclient import MailQueueClient

import smtplib
import email.utils
from email.mime.text import MIMEText

pytestmark = []

logging.basicConfig(level=logging.DEBUG)


# If sharing the server outside of a docker container, bind to all interfaces
# SERVER_QUEUE_HOST = "*" 

SERVER_QUEUE_HOST = "127.0.0.1"
CLIENT_QUEUE_HOST = "127.0.0.1"
QUEUE_PORT = 5563
SMTP_HOST = "0.0.0.0"
SMTP_PORT = 1025


@pytest.fixture(scope='session')
def mqserver(request):

    server = MailQueueServer(
            SERVER_QUEUE_HOST, QUEUE_PORT, SMTP_HOST, SMTP_PORT)

    # store emails for debugging and testing purposes
    server.store_emails = True

    server.start()

    def fin():
        server.stop()

    request.addfinalizer(fin)

    return server


@pytest.fixture(scope='function')
def mqclient(request, mqserver):

    client = MailQueueClient(CLIENT_QUEUE_HOST, QUEUE_PORT)

    # do client.start() in the test,
    # to allow the test to set the filter_pattern

    def fin():
        client.stop()

    request.addfinalizer(fin)

    return client


class TestMailQueueServer(object):

    @pytest.fixture(autouse=True)
    def setup(self, mqserver):
        """
        """

        self.server = mqserver


    def send_email(self, fromaddr, toaddr, subject, body, attachments=[]):

        # Create the message
        msg = MIMEText(body)
        msg['To'] = email.utils.formataddr(('Recipient',toaddr))
        msg['From'] = email.utils.formataddr(('Author',fromaddr))
        msg['Subject'] = subject

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)

        server.sendmail(fromaddr, [toaddr], msg.as_string())
        server.quit()


    def test_send_receive_mail_debug_queue(self):
        """
        """

        fromaddr = "author@example.com"
        toaddr = "recipient@example.com"
        subject = "email subject"
        body = "email body"

        self.send_email(fromaddr, toaddr, subject, body)

        # retrieve the message from the debug queue
        message = self.server.queue.get()
        self.server.queue.task_done()

        # check that the message is not empty
        assert message is not None
        assert len(message) > 0


    def test_send_receive_mail_message_queue(self,mqclient):
        """
        """

        # start up the mailqueue client
        # use default filter
        mqclient.start()

        fromaddr = "author@example.com"
        toaddr = "recipient@example.com"
        subject = "email subject"
        body = "email body"

        self.send_email(fromaddr, toaddr, subject, body)

        # retrieve the message from the client message queue
        message = mqclient.messages.get()
        mqclient.messages.task_done()

        # check that the message is not empty
        assert message is not None
        assert len(message) > 0
