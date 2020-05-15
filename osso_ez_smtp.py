from collections import namedtuple
from urllib.parse import urlparse
from email.mime.text import MIMEText
import os
import smtplib

# The SMTP_URI has an easy scheme.
# SMTP_URI = 'smtp://USER:PASS@HOST:PORT/'

__all__ = (
    'EnvSMTPSender', 'parse_uri',
    'From', 'To', 'Cc', 'Bcc')

SMTPConninfo = namedtuple(
    'SMTPConninfo', 'host port username password')


def parse_uri(uri):
    # TODO: SSL/TLS
    # SMTP_URI = 'smtp://USER:PASS@HOST:PORT/'
    parsed = urlparse(uri)
    assert parsed.scheme == 'smtp', parsed
    host = parsed.hostname
    port = parsed.port or 25
    path = parsed.path or '/'
    assert path == '/', parsed
    (username, password) = (parsed.username, parsed.password)
    assert not parsed.query and not parsed.fragment, parsed
    assert bool(parsed.username) == bool(parsed.password), parsed
    return SMTPConninfo(
        host=host, port=port, username=username, password=password)


class BaseAddr(object):
    def __init__(self, email):
        self._email = email

    def to_addr(self):
        return self._email

    def __str__(self):
        return self._email  # TODO: "Name" <email>


class From(BaseAddr):
    pass


class To(BaseAddr):
    pass


class Cc(BaseAddr):
    pass


class Bcc(BaseAddr):
    pass


class EnvSMTPSender(object):
    def __init__(self):
        self._smtpc = parse_uri(os.getenv('SMTP_URI', ''))

    def send_easy(self, recipients, subject, plain_body, from_addr=None):
        if not isinstance(from_addr, BaseAddr):
            from_addr = From(from_addr or self._smtpc.username)

        to_all = [  # convert to BaseAddr
            (To(i), i)[isinstance(i, BaseAddr)] for i in recipients]
        to_list = [str(i) for i in to_all if isinstance(i, To)]
        cc_list = [str(i) for i in to_all if isinstance(i, Cc)]

        msg = MIMEText(plain_body)
        msg['Subject'] = subject
        msg['From'] = str(from_addr)
        if to_list:
            msg['To'] = ', '.join(to_list)
        if cc_list:
            msg['Cc'] = ', '.join(cc_list)

        return self.send(
            recipients=to_all, emailmessage=msg, from_=from_addr)

    def send(self, recipients, emailmessage, from_=None):
        from_ = from_ or From(self._smtpc.username)
        with smtplib.SMTP(
                host=self._smtpc.host, port=self._smtpc.port) as smtp:
            smtp.ehlo(name='osso-ez-smtp.internal')
            smtp.starttls()
            smtp.ehlo(name='osso-ez-smtp.internal')

            if self._smtpc.username:
                smtp.login(self._smtpc.username, self._smtpc.password)

            smtp.send_message(
                emailmessage, from_.to_addr(),
                [str(i) for i in recipients])


if __name__ == '__main__':
    import sys
    sender = EnvSMTPSender()
    sender.send_easy(
        recipients=(sys.argv[1],), subject=sys.argv[2],
        plain_body=sys.argv[3])
