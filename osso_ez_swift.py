# This is very WIP; do not use directly
# requires: keystone-light>=0.3
# requires: osso_ez_gpg>=0.3
# requires: (local)settings
import sys

from keystone_light import (
    Cloud, DirectConfig,
    ChunkIteratorIOBaseWrapper, SwiftContainerGetPipe,
    TemporaryUntilClosedFile)

from osso_ez_gpg import DeflatePipe, InflatePipe, DecryptPipe, EncryptPipe

import settings


if __name__ == '__main__':
    def encrypted_name(name):
        return '{}.qz1.gpg'.format(name)

    config = DirectConfig(settings.KEYSTONE_URI)
    project = Cloud(config).get_current_project()
    assert project.get_fullname() == settings.SWIFT_PROJECT, (
        project.get_fullname())

    swift = project.get_swift()
    container = swift.get_container(settings.SWIFT_CONTAINER)

    if sys.argv[1] in ('-r', '-R'):

        with_enc = (sys.argv[1] == '-r')
        for cleartext_name in sys.argv[2:]:
            remote_name = (
                encrypted_name(cleartext_name) if with_enc
                else cleartext_name)

            print('downloading to', cleartext_name)
            if with_enc:
                with TemporaryUntilClosedFile(cleartext_name) as outfp, \
                        SwiftContainerGetPipe(
                            container, remote_name) as pipe1, \
                        DecryptPipe(
                            pipe1.stdout,
                            password=settings.PASSPHRASE_VALUE) as pipe2, \
                        InflatePipe(pipe2.stdout, outfp) as pipe3:
                    pipe3.communicate()
                    pipe2.communicate()
                    pipe1.communicate()
            else:
                with TemporaryUntilClosedFile(cleartext_name) as outfp, \
                        SwiftContainerGetPipe(
                            container, remote_name, outfp) as pipe1:
                    pipe1.communicate()

    elif sys.argv[1] in ('-w', '-W'):

        with_enc = (sys.argv[1] == '-w')
        for cleartext_name in sys.argv[2:]:
            remote_name = (
                encrypted_name(cleartext_name) if with_enc
                else cleartext_name)

            print('uploading to', remote_name)
            try:
                container.delete(remote_name)
            except FileNotFoundError:
                pass

            if with_enc:
                with open(cleartext_name, 'rb') as source, \
                        DeflatePipe(source) as pipe1, \
                        EncryptPipe(
                            pipe1.stdout,
                            password=settings.PASSPHRASE_VALUE) as pipe2:
                    container.put(
                        remote_name, ChunkIteratorIOBaseWrapper(pipe2.stdout))
                    pipe2.communicate()
                    pipe1.communicate()
            else:
                with open(cleartext_name, 'rb') as source:
                    # No need for ChunkIteratorIOBaseWrapper because
                    # source has a length.
                    container.put(remote_name, source)

    else:
        assert False, sys.argv
