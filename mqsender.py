#!/usr/bin/env python

import argparse
import email.utils
import smtplib

from email.mime.text import MIMEText


# parse arguments and options
parser = argparse.ArgumentParser()

parser.add_argument("--mail-host",
                    help="mail host",
                    default="127.0.0.1",
                    type=str)

parser.add_argument("--mail-port",
                    help="mail port",
                    default=1025,
                    type=int)

parser.add_argument("--to",
                    help="email recipient",
                    # action='append',
                    default="recipient@example.com",
                    type=str)

opts = parser.parse_args()


# Create the message
msg = MIMEText('This is the body of the message.')
msg['To'] = email.utils.formataddr(('Recipient',opts.to))
msg['From'] = email.utils.formataddr(('Author','author@example.com'))
msg['Subject'] = 'Simple text message'

server = smtplib.SMTP(opts.mail_host,opts.mail_port)
# server.set_debuglever(True)

try:
    server.sendmail('author@example.com',
                    [opts.to],
                    msg.as_string())
finally:
    server.quit()
