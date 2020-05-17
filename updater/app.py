"""
acme-cert-updater

update the certificate using ACME and Route 53
"""

import os
import os.path
import pathlib
import json
import string
import tempfile
import traceback
from datetime import datetime
from typing import Dict, Union, List
from unittest import mock

import logging
import boto3
from botocore.exceptions import ClientError
import importlib
import certbot.main
import configobj

logger = logging.getLogger(__name__)
logging.getLogger().setLevel(log_level())

def log_level() -> int:
    level = os.environ.get('UPDATER_LOG_LEVEL', 'ERROR')
    if level == 'DEBUG':
        return logging.DEBUG
    if level == 'INFO':
        return logging.INFO
    if level == 'WARN':
        return logging.WARN
    if level == 'WARNING':
        return logging.WARNING
    if level == 'ERROR':
        return logging.ERROR
    if level == 'CRITICAL':
        return logging.CRITICAL
    raise ValueError("unknown log level " + level)

class Config:
    """configure of acme-cert-update"""

    def __init__(self, event):
        """initialize Config"""
        domains = event.get('domains', '')
        if isinstance(domains, str):
            # the domains field is comma separated string
            self.__domains = domains.split(',')
        elif isinstance(domains, List):
            self.__domains = domains
        else:
            raise ValueError("invalid domains")
        self.__domains = [
            domain.strip().lower() for domain in self.__domains
                if isinstance(domain, str) and domain.strip() != ''
        ]

        cert_name = event.get('cert_name', '')
        if cert_name == '':
            if len(self.__domains) > 0:
                self.__cert_name = Config._trim_wildcard(self.__domains[0])
            else:
                self.__cert_name = ''
        else:
            self.__cert_name = cert_name.lower()

    @classmethod
    def _trim_wildcard(cls, domain: str) -> str:
        if domain.startswith('*.'):
            return domain[2:]
        return domain

    @property
    def domains(self) -> List[str]:
        """domain names for issue"""
        return self.__domains

    @property
    def cert_name(self) -> str:
        return self.__cert_name

    @property
    def email(self) -> str:
        """Email address"""
        return os.environ.get('UPDATER_EMAIL', '')

    @property
    def bucket_name(self) -> str:
        """S3 bucket name for saving the certificates"""
        return os.environ.get('UPDATER_BUCKET_NAME', '')

    @property
    def prefix(self) -> str:
        """Prefix of objects on S3 bucket"""
        return os.environ.get('UPDATER_PREFIX', '')

    @property
    def environment(self) -> str:
        """execution environment"""
        return os.environ.get('UPDATER_ENVIRONMENT', '')

    @property
    def acme_server(self) -> str:
        """url for acme server"""
        return os.environ.get(
            'UPDATER_ACME_SERVER',
            'https://acme-v02.api.letsencrypt.org/directory'
        )

    @property
    def notification(self) -> str:
        """The Amazon SNS topic Amazon Resource Name (ARN) to which the updater reports events."""
        return os.environ.get('UPDATER_NOTIFICATION', '')


def certonly(config) -> None:
    """get new certificate"""
    with tempfile.TemporaryDirectory() as tmp:
        input_array = [
            'certonly',
            '--noninteractive',
            '--agree-tos',
            '--email', config.email,
            '--dns-route53',
            '--config-dir', os.path.join(tmp, 'config-dir/'),
            '--work-dir', os.path.join(tmp, 'word-dir/'),
            '--logs-dir', os.path.join(tmp, 'logs-dir/'),
            '--cert-name', config.cert_name,
        ]

        for domain in config.domains:
            input_array.append('--domains')
            input_array.append(domain)

        if config.environment == 'production':
            input_array.append('--server')
            input_array.append(config.acme_server)
        else:
            input_array.append('--staging')

        certbot_main(input_array)
        save_cert(config, tmp)

def renew(config) -> None:
    """update existing certificate"""
    with tempfile.TemporaryDirectory() as tmp:
        load_cert(config, tmp)

        flag = pathlib.Path(tmp, 'flag.txt')
        hook = pathlib.Path(tmp, 'config-dir', 'renewal-hooks', 'post', 'post.sh')
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/usr/bin/env bash\n\ntouch '" + str(flag) + "'")
        hook.chmod(0o755)

        input_array = [
            'renew',
            '--noninteractive',
            '--agree-tos',
            '--email', config.email,
            '--dns-route53',
            '--config-dir', os.path.join(tmp, 'config-dir/'),
            '--work-dir', os.path.join(tmp, 'word-dir/'),
            '--logs-dir', os.path.join(tmp, 'logs-dir/'),
        ]
        if config.environment != 'production':
            # force renewal for testing
            input_array.append('--force-renewal')
            # connect to the staging environment
            input_array.append('--staging')

        certbot_main(input_array)
        if flag.exists():
            save_cert(config, tmp)

class mock_atexit:
    """patch certbot.util.atexit"""

    def __init__(self):
        patch = mock.patch("certbot.util.atexit")
        self._patch = patch
        self._func = []

    def register(self, func, *args, **kwargs):
        """register dummy atexit"""
        self._func.append([func, args, kwargs])

    def atexit_call(self):
        """call atexit functions"""
        for func, args, kwargs in reversed(self._func):
            func(*args, **kwargs)
        self._func = []

    def __enter__(self):
        result = self._patch.start()
        register = result.register
        register.side_effect = self.register
        return self

    def __exit__(self, ex_type, ex_value, trace):
        self._patch.stop()
        self.atexit_call()

def certbot_main(args: List[str]) -> None:
    """
    certbot_main is a wrapper of certbot.main.main.
    certbot.main.main overwrites the global configures,
    so certbot_main save and restore them.
    """

    with mock_atexit():
        # disable certbot custom log handler.
        with mock.patch("certbot._internal.log.pre_arg_parse_setup"):
            with mock.patch("certbot._internal.log.post_arg_parse_setup"):

                # call main function
                certbot.main.main(args)


s3 = boto3.resource('s3') # pylint: disable=invalid-name
def save_cert(config, tmp: str) -> None:
    """upload the certificate files to Amazon S3"""
    bucket_name = config.bucket_name
    key = build_key(config.prefix, config.cert_name + '.json')
    bucket = s3.Bucket(config.bucket_name)
    now = datetime.utcnow().isoformat()
    live = os.path.join(tmp, 'config-dir/live/', config.cert_name)
    for filename in ['cert.pem', 'chain.pem', 'fullchain.pem', 'privkey.pem']:
        logger.debug(f'uploading {filename}')
        bucket.upload_file(
            os.path.join(live, filename),
            build_key(config.prefix, config.cert_name, now, filename),
        )

    certconfig = {
        'timestamp': now,
        'domain': config.cert_name, # for backward compatibility
        'domains': config.domains,
        'cert_name': config.cert_name,
        'config': {
            'account': get_files(tmp, 'config-dir/accounts'),
            'csr': get_files(tmp, 'config-dir/csr'),
            'keys': get_files(tmp, 'config-dir/keys'),
            'renewal': get_renewal_config(tmp, config.cert_name),
        },
        'cert': {
            'cert': build_key(config.prefix, config.cert_name, now, 'cert.pem'),
            'chain': build_key(config.prefix, config.cert_name, now, 'chain.pem'),
            'fullchain': build_key(config.prefix, config.cert_name, now, 'fullchain.pem'),
            'privkey': build_key(config.prefix, config.cert_name, now, 'privkey.pem'),
        },
    }

    logger.debug(f'uploading the certificate information to s3://{bucket_name}/{key}')
    bucket.put_object(
        Body=json.dumps(certconfig),
        Key=key,
        ContentType='application/json',
    )
    notify_renewed(config, certconfig, key)

def load_cert(config, tmp: str) -> None:
    """download the certificate files from Amazon S3"""
    bucket_name = config.bucket_name
    key = build_key(config.prefix, config.cert_name + '.json')
    logger.debug(f'downloading the certificate from s3://{bucket_name}/{key}')
    bucket = s3.Bucket(bucket_name)
    obj = bucket.Object(key)
    certconfig = json.load(obj.get()['Body'])

    set_files(tmp, 'config-dir/accounts/', certconfig['config']['account'])
    set_files(tmp, 'config-dir/csr/', certconfig['config']['csr'])
    set_files(tmp, 'config-dir/keys/', certconfig['config']['keys'])
    set_renewal_config(tmp, config.cert_name, certconfig['config']['renewal'])

    archive = os.path.join(tmp, 'config-dir', 'archive', config.cert_name)
    pathlib.Path(archive).mkdir(parents=True, exist_ok=True)
    cert = certconfig['cert']
    bucket.download_file(cert['cert'], os.path.join(archive, 'cert1.pem'))
    bucket.download_file(cert['chain'], os.path.join(archive, 'chain1.pem'))
    bucket.download_file(cert['fullchain'], os.path.join(archive, 'fullchain1.pem'))
    bucket.download_file(cert['privkey'], os.path.join(archive, 'privkey1.pem'))

    live = os.path.join(tmp, 'config-dir', 'live', config.cert_name)
    pathlib.Path(live).mkdir(parents=True, exist_ok=True)
    os.symlink(os.path.join(archive, 'cert1.pem'), os.path.join(live, 'cert.pem'))
    os.symlink(os.path.join(archive, 'chain1.pem'), os.path.join(live, 'chain.pem'))
    os.symlink(os.path.join(archive, 'fullchain1.pem'), os.path.join(live, 'fullchain.pem'))
    os.symlink(os.path.join(archive, 'privkey1.pem'), os.path.join(live, 'privkey.pem'))

def get_files(tmp: str, subdir: str) -> Dict[str, str]:
    """get_files gets file contents as dict"""
    config = {}
    path = pathlib.Path(tmp, subdir)
    for root, _, files in os.walk(str(path)):
        for name in files:
            filepath = pathlib.Path(root, name)
            config[str(filepath.relative_to(path))] = filepath.read_text()
    return config

def set_files(tmp: str, subdir: str, config: Dict[str, str]) -> None:
    """extract config to file system"""
    path = pathlib.Path(tmp, subdir)
    for key, value in config.items():
        filepath = path.joinpath(key)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(value)

def get_renewal_config(tmp: str, domain: str) -> configobj.ConfigObj:
    """return renewal config of certbot"""
    config = {}
    tmppath = pathlib.Path(tmp)
    cfg = configobj.ConfigObj(os.path.join(tmp, 'config-dir', 'renewal', domain + '.conf'))
    for key in ['archive_dir', 'cert', 'privkey', 'chain', 'fullchain']:
        path = pathlib.Path(cfg[key])
        cfg[key] = str(path.relative_to(tmppath))
    for key in ['config_dir', 'work_dir', 'logs_dir']:
        path = pathlib.Path(cfg['renewalparams'][key])
        cfg['renewalparams'][key] = str(path.relative_to(tmppath))
    for key, value in cfg.items():
        config[key] = value
    return config

def set_renewal_config(tmp: str, domain: str, config: configobj.ConfigObj) -> None:
    """write renewal config of certbot to file system"""
    tmppath = pathlib.Path(tmp)
    for key in ['archive_dir', 'cert', 'privkey', 'chain', 'fullchain']:
        config[key] = str(pathlib.Path(tmppath / config[key]))
    for key in ['config_dir', 'work_dir', 'logs_dir']:
        config['renewalparams'][key] = str(pathlib.Path(tmppath / config['renewalparams'][key]))

    ret = configobj.ConfigObj()
    conf_path = pathlib.Path(tmp, 'config-dir', 'renewal', domain + '.conf')
    conf_path.parent.mkdir(parents=True, exist_ok=True)
    ret.filename = str(conf_path)
    for key, value in config.items():
        ret[key] = value
    ret.write()


def build_key(*segment) -> str:
    """build a key of S3 objects"""
    path = "/".join(segment)
    path = path.replace("//", "/")
    if len(path) > 1 and path[0] == "/":
        path = path[1:]
    return path

sns = boto3.client('sns') # pylint: disable=invalid-name
def notify_renewed(config, certconfig: Dict[str, Union[str, Dict[str, str]]], key: str) -> None:
    """notify via SNS topic"""
    if config.notification == '':
        return
    template = string.Template("""Notification from acme-cert-updater(https://github.com/shogo82148/acme-cert-updater).
The following certificate is renewed.

- cert_name: $cert_name
- domains: $domains
- bucket: $bucket
- object key: $key
  - cert: $cert
  - chain: $chain
  - fullchain: $fullchain
  - privkey: $privkey
""")
    text_message = template.substitute(
        timestamp = certconfig['timestamp'],
        domains = ', '.join(config.domains),
        cert_name = config.cert_name,
        bucket = config.bucket_name,
        key = key,
        cert = certconfig['cert']['cert'],
        chain = certconfig['cert']['chain'],
        fullchain = certconfig['cert']['fullchain'],
        privkey = certconfig['cert']['privkey'],
    )
    json_message = json.dumps({
        'type': 'renewed',
        'timestamp': certconfig['timestamp'],
        'domain': config.cert_name, # for backward compatibility
        'domains': config.domains,
        'cert_name': config.cert_name,
        'bucket': config.bucket_name,
        'key': key,
        'cert': certconfig['cert'],
    })
    message = json.dumps({
        'default': json_message,
        'email': text_message,
    })
    sns.publish(
        TopicArn=config.notification,
        Message=message,
        MessageStructure="json",
    )

def notify_failed(config, err) -> None:
    """notify via SNS topic"""
    if config.notification == '':
        return
    template = string.Template("""Notification from acme-cert-updater(https://github.com/shogo82148/acme-cert-updater).
Certificate renewal is failed.

- cert_name: $cert_name
- domains: $domains

Exception:
$err
""")
    text_message = template.substitute(
        domains = ', '.join(config.domains),
        cert_name = config.cert_name,
        err = err,
    )
    json_message = json.dumps({
        'type': 'failed',
        'domains': config.domains,
        'cert_name': config.cert_name,
    })
    message = json.dumps({
        'default': json_message,
        'email': text_message,
    })
    sns.publish(
        TopicArn=config.notification,
        Message=message,
        MessageStructure="json",
    )

def needs_init(config) -> bool:
    """check initialize is required"""
    bucket_name = config.bucket_name
    key = build_key(config.prefix, config.cert_name + '.json')
    logger.debug(f'checking s3://{bucket_name}/{key} exists.')
    bucket = s3.Bucket(bucket_name)
    obj = bucket.Object(key)
    try:
        obj.load()
    except ClientError:
        return True
    return False

def lambda_handler(event, context): # pylint: disable=unused-argument
    """entry point of AWS Lambda"""

    config = Config(event)
    if len(config.domains) == 0:
        # nothing to do
        return {}

    try:
        if needs_init(config):
            try:
                logger.debug('update the certificate.')
                certonly(config)
            except:
                logger.debug('updating failed. fall back to request new certificate.')
                renew(config)
        else:
            logger.debug('request new certificate.')
            renew(config)
    except:
        notify_failed(config, traceback.format_exc())
        raise

    return {}

if __name__ == "__main__":
    lambda_handler({}, None)
