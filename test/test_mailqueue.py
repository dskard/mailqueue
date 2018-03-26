import email
import logging
import os
import pytest
import queue
import smtplib

from email.utils import COMMASPACE, formataddr
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from mqserver import MailQueueServer
from mqclient import MailQueueClient

pytestmark = []

logging.basicConfig(level=logging.DEBUG)


# If sharing the server outside of a docker container, bind to all interfaces
# SERVER_QUEUE_HOST = "*" 

SERVER_QUEUE_HOST = "127.0.0.1"
CLIENT_QUEUE_HOST = "127.0.0.1"
QUEUE_PORT = 5563
SMTP_HOST = "0.0.0.0"
SMTP_PORT = 1025

ATTACHMENTS_DIR = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'attachments')

QUEUE_GET_TIMEOUT = 2

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


@pytest.fixture(scope='session')
def sendmail():

    def send_email(fromaddr: str, toaddrs: list, subject: str,
            body: str, attachments=[]):
        """helper function for sending emails

        fromaddr : string of sender email address
        toaddrs : list of recipient email addresses
        """

        # Create the message
        msg = MIMEMultipart()
        msg['To'] = COMMASPACE.join(toaddrs)
        msg['From'] = formataddr(('Author',fromaddr))
        msg['Subject'] = subject
        msg.attach(MIMEText(body))

        # Attach attachments
        for fname in attachments:
            with open(fname,'rb') as f:
                # create the attachment
                part = MIMEApplication(f.read(), Name=os.path.basename(fname))
            # save the attachment to the message
            part['Content-Disposition'] = \
                'attachment; filename="%s"' % os.path.basename(fname)
            msg.attach(part)


        # Send the message
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.sendmail(fromaddr, toaddrs, msg.as_string())
        server.quit()

        return msg

    return send_email


@pytest.fixture(scope='session')
def msgcmp():

    def compare_emails(sent_msg, recv_msg):
        """helper function for comparing messages"""

        # check that it is a multipart message
        assert sent_msg.is_multipart() == recv_msg.is_multipart()

        sent_msg_parts = sent_msg.get_payload()
        recv_msg_parts = recv_msg.get_payload()

        # should be two parts, body (text) and file data (application)
        assert len(sent_msg_parts) == len(recv_msg_parts)

        for i in range(len(sent_msg_parts)):

            sent_msg_part = sent_msg_parts[i].get_payload(decode=True)
            recv_msg_part = recv_msg_parts[i].get_payload(decode=True)

            # received body should match sent body
            assert recv_msg_part == sent_msg_part

    return compare_emails


class TestMailQueueServer(object):

    @pytest.fixture(autouse=True)
    def setup(self, mqserver, sendmail, msgcmp):
        """
        """

        self.server = mqserver
        self.sendmail = sendmail
        self.msgcmp = msgcmp


    @pytest.mark.asyncio
    async def test_send_receive_mail_debug_queue(self):
        """
        """

        fromaddr = "author@example.com"
        toaddrs = ["recipient@example.com"]
        subject = "email subject"
        body = "email body"

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body)

        # retrieve the message from the debug queue
        msg_bytes = await self.server.queue.get()
        self.server.queue.task_done()

        # check that the message is not empty
        assert len(msg_bytes) > 0

        # convert the message from types to a message
        recv_msg = email.message_from_bytes(msg_bytes)

        self.msgcmp(sent_msg, recv_msg)


    @pytest.mark.asyncio
    async def test_send_attachment_text(self):
        """
        """

        fromaddr = "author@example.com"
        toaddrs = ["recipient@example.com"]
        subject = "email subject"
        body = "email body"
        attachments=[os.path.join(ATTACHMENTS_DIR,'hello.txt')]

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body, attachments)

        # retrieve the message from the debug queue
        msg_bytes = await self.server.queue.get()
        self.server.queue.task_done()

        # convert the message from types to a message
        recv_msg = email.message_from_bytes(msg_bytes)

        self.msgcmp(sent_msg, recv_msg)


    @pytest.mark.asyncio
    async def test_send_attachment_tgz(self):
        """
        """

        fromaddr = "author@example.com"
        toaddrs = ["recipient@example.com"]
        subject = "email subject"
        body = "email body"
        attachments=[os.path.join(ATTACHMENTS_DIR,'hello.tgz')]

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body, attachments)

        # retrieve the message from the debug queue
        msg_bytes = await self.server.queue.get()
        self.server.queue.task_done()

        # convert the message from types to a message
        recv_msg = email.message_from_bytes(msg_bytes)

        self.msgcmp(sent_msg, recv_msg)




class TestMailQueueClient(object):

    @pytest.fixture(autouse=True)
    def setup(self, mqserver, mqclient, sendmail, msgcmp):
        """
        """

        self.server = mqserver
        self.client = mqclient
        self.sendmail = sendmail
        self.msgcmp = msgcmp


    def test_send_receive_mail_message_queue(self):
        """
        """

        # start up the mailqueue client
        # use default filter
        self.client.start()

        fromaddr = "author@example.com"
        toaddrs = ["recipient@example.com"]
        subject = "email subject"
        body = "email body"

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body)

        # retrieve the message from the client message queue
        msg_bytes = self.client.messages.get()
        self.client.messages.task_done()

        # check that the message is not empty
        assert len(msg_bytes) > 0

        # convert the message from types to a message
        recv_msg = email.message_from_bytes(msg_bytes)

        self.msgcmp(sent_msg, recv_msg)


    def test_send_attachment_text(self):
        """
        """

        # start up the mailqueue client
        # use default filter
        self.client.start()

        fromaddr = "author@example.com"
        toaddrs = ["recipient@example.com"]
        subject = "email subject"
        body = "email body"
        attachments=[os.path.join(ATTACHMENTS_DIR,'hello.txt')]

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body, attachments)

        # retrieve the message from the client message queue
        msg_bytes = self.client.messages.get()
        self.client.messages.task_done()

        # convert the message from types to a message
        recv_msg = email.message_from_bytes(msg_bytes)

        self.msgcmp(sent_msg, recv_msg)


    def test_send_attachment_tgz(self):
        """
        """

        # start up the mailqueue client
        # use default filter
        self.client.start()

        fromaddr = "author@example.com"
        toaddrs = ["recipient@example.com"]
        subject = "email subject"
        body = "email body"
        attachments=[os.path.join(ATTACHMENTS_DIR,'hello.tgz')]

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body, attachments)

        # retrieve the message from the client message queue
        msg_bytes = self.client.messages.get()
        self.client.messages.task_done()

        # convert the message from types to a message
        recv_msg = email.message_from_bytes(msg_bytes)

        self.msgcmp(sent_msg, recv_msg)


    def test_message_filter_single_toaddr(self):
        """filtering based on a single toaddr should work"""

        # start up the mailqueue client
        # use default filter
        self.client.filter_pattern = "recipient@example.com"
        self.client.start()

        fromaddr = "author@example.com"
        toaddrs = ["recipient@example.com"]
        subject = "email subject"
        body = "email body"

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body)

        # retrieve the message from the client message queue
        msg_bytes = self.client.messages.get()
        self.client.messages.task_done()

        # convert the message from types to a message
        recv_msg = email.message_from_bytes(msg_bytes)

        self.msgcmp(sent_msg, recv_msg)


    def test_message_filter_multiple_toaddrs_in_order(self):
        """filtering based on a multiple toaddrs in order should work"""

        # start up the mailqueue client
        # use default filter
        self.client.filter_pattern = \
                "recipient1@example.com, recipient2@example.com"
        self.client.start()

        fromaddr = "author@example.com"
        toaddrs = ["recipient1@example.com", "recipient2@example.com"]
        subject = "email subject"
        body = "email body"

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body)

        # retrieve the message from the client message queue
        msg_bytes = self.client.messages.get()
        self.client.messages.task_done()

        # convert the message from types to a message
        recv_msg = email.message_from_bytes(msg_bytes)

        self.msgcmp(sent_msg, recv_msg)


    def test_message_filter_multiple_toaddrs_partial_begin(self):
        """filtering based on partial toaddrs (match at beginning) should work"""

        # start up the mailqueue client
        # use default filter
        self.client.filter_pattern = "recipient1@example.com"
        self.client.start()

        fromaddr = "author@example.com"
        toaddrs = ["recipient1@example.com", "recipient2@example.com"]
        subject = "email subject"
        body = "email body"

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body)

        # retrieve the message from the client message queue
        msg_bytes = self.client.messages.get()
        self.client.messages.task_done()

        # convert the message from types to a message
        recv_msg = email.message_from_bytes(msg_bytes)

        self.msgcmp(sent_msg, recv_msg)


    def test_message_filter_multiple_toaddrs_partial_middle(self):
        """filtering based on partial toaddrs (match in middle) should fail"""

        # start up the mailqueue client
        # use default filter
        self.client.filter_pattern = "recipient2@example.com"
        self.client.start()

        fromaddr = "author@example.com"
        toaddrs = ["recipient1@example.com", "recipient2@example.com"]
        subject = "email subject"
        body = "email body"

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body)

        # retrieve message from client message queue should fail
        with pytest.raises(queue.Empty):
            self.client.messages.get(timeout=QUEUE_GET_TIMEOUT)


    def test_message_filter_single_fromaddr(self):
        """filtering based on the fromaddr should not work"""

        # start up the mailqueue client
        # use default filter
        self.client.filter_pattern = "author@example.com"
        self.client.start()

        fromaddr = "author@example.com"
        toaddrs = ["recipient@example.com"]
        subject = "email subject"
        body = "email body"

        sent_msg = self.sendmail(fromaddr, toaddrs, subject, body)

        # retrieve message from client message queue should fail
        with pytest.raises(queue.Empty):
            self.client.messages.get(timeout=QUEUE_GET_TIMEOUT)


