#!/usr/bin/env python3
#
# Based on the results of:
# https://wjd.nu/notes/2020#encryption-vocabulary-long-term-storage
#
# Usage: osso_ez_gpg.py -e ./password.txt <SOURCE >ENCRYPTED
# Usage: osso_ez_gpg.py -d ./password.txt <ENCRYPTED >SOURCE
#
import os
import os.path
import sys

from subprocess import CalledProcessError, Popen, PIPE

GPG_BIN = 'gpg'
DEFLATE_BIN = 'qlzip1'
INFLATE_BIN = 'qlzcat1'


def which(application):
    "Turn a xyz into /usr/bin/xyz based on that PATH envvar"
    if '/' not in application:
        for path in os.environ.get('PATH', '/usr/bin:/bin').split(':'):
            if os.path.exists(os.path.join(path, application)):
                application = os.path.join(path, application)
                break
        else:
            raise FileNotFoundError(application)
    return os.path.abspath(application)


class Pipe(Popen):
    BIN = NotImplemented

    @classmethod
    def _get_bin(cls):
        if '/' not in cls.BIN:
            cls.BIN = which(cls.BIN)
        return cls.BIN

    def __init__(self, stdin, stdout=PIPE, args=None):
        args = args or [self._get_bin()]
        super().__init__(
            args=args, stdin=stdin, stdout=stdout, stderr=PIPE,
            close_fds=False)

    def communicate(self):
        out, err = super().communicate()
        assert out in (b'', None), out
        if self.returncode != 0:
            print('(stderr)', err.decode('ascii', 'replace'), file=sys.stderr)
            raise CalledProcessError(
                cmd=self.BIN, output=err,
                returncode=self.returncode)
        return (None, err)


class DeflatePipe(Pipe):
    BIN = DEFLATE_BIN


class InflatePipe(Pipe):
    BIN = INFLATE_BIN


class EncryptPipe(Pipe):
    BIN = GPG_BIN

    def __init__(self, stdin, stdout=PIPE, password=''):
        ior, iow = os.pipe2(0)  # os.pipe() would set O_CLOEXEC
        super().__init__(
            stdin=stdin, stdout=stdout, args=[
                # TODO: we'd like to avoid these:
                # gpg: directory '/home/osso/.gnupg' created
                # gpg: keybox '/home/osso/.gnupg/pubring.kbx' created
                self._get_bin(), '--batch',
                # Symmetric encryption using a password
                '--symmetric', '--passphrase-fd', str(ior),
                # Password derivation to a secret key
                '--s2k-mode', '3', '--s2k-digest-algo', 'SHA512',
                '--s2k-count', '65536',
                # No compression here; we do that using DEFLATE
                '--compress-algo', 'none',
                # AES-256 CFB
                '--cipher-algo', 'AES256',
            ])
        os.write(iow, '{}\n'.format(password).encode('ascii'))
        os.close(iow)
        os.close(ior)


class DecryptPipe(Pipe):
    BIN = GPG_BIN

    def __init__(self, stdin, stdout=PIPE, password=''):
        ior, iow = os.pipe2(0)  # os.pipe() would set O_CLOEXEC
        super().__init__(
            stdin=stdin, stdout=stdout, args=[
                # TODO: we'd like to avoid these:
                # gpg: directory '~/.gnupg' created
                # gpg: keybox '~/.gnupg/pubring.kbx' created
                self._get_bin(), '--batch',
                # Symmetric encryption using a password
                '--decrypt', '--passphrase-fd', str(ior),
            ])
        os.write(iow, '{}\n'.format(password).encode('ascii'))
        os.close(iow)
        os.close(ior)


def encrypt(infp, outfp, password):
    with DeflatePipe(infp) as pipe1, \
         EncryptPipe(pipe1.stdout, outfp, password=password) as pipe2:
        pipe2.communicate()
        pipe1.communicate()


def encrypt_no_compress(infp, outfp, password):
    with EncryptPipe(infp, outfp, password=password) as pipe1:
        pipe1.communicate()


def decrypt(infp, outfp, password):
    with DecryptPipe(infp, password=password) as pipe1, \
         InflatePipe(pipe1.stdout, outfp) as pipe2:
        pipe2.communicate()
        pipe1.communicate()


def decrypt_no_compress(infp, outfp, password):
    with DecryptPipe(infp, outfp, password=password) as pipe1:
        pipe1.communicate()


def encrypt_decrypt_test(infp, outfp, password):
    with DeflatePipe(infp) as pipe1, \
         EncryptPipe(pipe1.stdout, password=password) as pipe2, \
         DecryptPipe(pipe2.stdout, password=password) as pipe3, \
         InflatePipe(pipe3.stdout, outfp) as pipe4:
        pipe4.communicate()
        pipe3.communicate()
        pipe2.communicate()
        pipe1.communicate()


def encrypt_decrypt_test_no_compress(infp, outfp, password):
    with EncryptPipe(infp, password=password) as pipe1, \
            DecryptPipe(pipe1.stdout, outfp, password=password) as pipe2:
        pipe2.communicate()
        pipe1.communicate()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] in (
            '-d', '-D', '-e', '-E', '-t', '-T'):
        with open(sys.argv[2]) as passfp:
            password = passfp.read().strip()

        if sys.argv[1] == '-d':
            decrypt(sys.stdin.buffer, sys.stdout.buffer, password)
        elif sys.argv[1] == '-D':
            decrypt_no_compress(sys.stdin.buffer, sys.stdout.buffer, password)
        elif sys.argv[1] == '-e':
            encrypt(sys.stdin.buffer, sys.stdout.buffer, password)
        elif sys.argv[1] == '-E':
            encrypt_no_compress(sys.stdin.buffer, sys.stdout.buffer, password)
        elif sys.argv[1] == '-t':
            encrypt_decrypt_test(
                sys.stdin.buffer, sys.stdout.buffer, password)
        elif sys.argv[1] == '-T':
            encrypt_decrypt_test_no_compress(
                sys.stdin.buffer, sys.stdout.buffer, password)
    else:
        assert False, sys.argv
