"""tests of acme-cert-updater"""

import unittest
import secrets

import boto3
from typing import List
from updater import app

# pylint: disable=missing-docstring

AUTHOR_ACCOUNT = '445285296882'

class DummyConfig:
    def __init__(self):
        self._prefix = secrets.token_hex(16)

    @property
    def domains(self) -> List[str]:
        return ['shogo82148.com', '*.shogo82148.com', '*.acme.shogo82148.com']

    @property
    def cert_name(self) -> str:
        return 'example.com'

    @property
    def email(self) -> str:
        return "shogo82148@gmail.com"

    @property
    def bucket_name(self) -> str:
        return "shogo82148-acme-cert-updater-test"

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def environment(self) -> str:
        return 'staging'

    @property
    def acme_server(self) -> str:
        return 'https://acme-v02.api.letsencrypt.org/directory'

    @property
    def notification(self) -> str:
        # pylint: disable=line-too-long
        return 'arn:aws:sns:ap-northeast-1:445285296882:acme-cert-updater-test-UpdateTopic-141WK4DP5P40E'

class TestIntegration(unittest.TestCase):
    def setUp(self):
        identity = {}
        try:
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
        except:
            self.skipTest("external resource not available")

        if identity.get('Account') != AUTHOR_ACCOUNT:
            self.skipTest("external resource not available")

        self.__config = DummyConfig()
    
    def tearDown(self):
        cfg = self.__config
        s3 = boto3.resource('s3') # pylint: disable=invalid-name
        s3.Bucket(cfg.bucket_name).objects.filter(
            Prefix=cfg.prefix+'/',
        ).delete()

    def test_certonly(self):
        cfg = self.__config
        assert app.needs_init(cfg)
        app.certonly(cfg)

        assert not app.needs_init(cfg)
        app.renew(cfg)

if __name__ == '__main__':
    unittest.main()
