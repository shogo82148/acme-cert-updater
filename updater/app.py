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
from datetime import datetime
from typing import Dict, Union

import logging
import boto3
from botocore.exceptions import ClientError
import certbot.main
import configobj

# set up the logger
logging.basicConfig(level=logging.INFO)

class Config:
    """configure of acme-cert-update"""

    @property
    def domains(self) -> str:
        """Comma separated list of domains to update the certificates"""
        return os.environ.get('UPDATER_DOMAINS', '')

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
            '-d', config.domains,
            '--config-dir', os.path.join(tmp, 'config-dir/'),
            '--work-dir', os.path.join(tmp, 'word-dir/'),
            '--logs-dir', os.path.join(tmp, 'logs-dir/'),
        ]
        if config.environment == 'production':
            input_array.append('--server')
            input_array.append(config.acme_server)
        else:
            input_array.append('--staging')
        certbot.main.main(input_array)
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

        certbot.main.main(input_array)

        if flag.exists():
            save_cert(config, tmp)

s3 = boto3.resource('s3') # pylint: disable=invalid-name
def save_cert(config, tmp: str) -> None:
    """upload the certificate files to Amazon S3"""
    bucket = s3.Bucket(config.bucket_name)
    domains = set(domain.strip().replace('*.', '', 1) for domain in config.domains.split(','))
    now = datetime.utcnow().isoformat()
    for domain in domains:
        live = os.path.join(tmp, 'config-dir/live/', domain)
        for filename in ['cert.pem', 'chain.pem', 'fullchain.pem', 'privkey.pem']:
            bucket.upload_file(
                os.path.join(live, filename),
                build_key(config.prefix, domain, now, filename),
            )

        certconfig = {
            'timestamp': now,
            'domain': domain,
            'config': {
                'account': get_files(tmp, 'config-dir/accounts'),
                'csr': get_files(tmp, 'config-dir/csr'),
                'keys': get_files(tmp, 'config-dir/keys'),
                'renewal': get_renewal_config(tmp, domain),
            },
            'cert': {
                'cert': build_key(config.prefix, domain, now, 'cert.pem'),
                'chain': build_key(config.prefix, domain, now, 'chain.pem'),
                'fullchain': build_key(config.prefix, domain, now, 'fullchain.pem'),
                'privkey': build_key(config.prefix, domain, now, 'privkey.pem'),
            },
        }
        bucket.put_object(
            Body=json.dumps(certconfig),
            Key=build_key(config.prefix, domain + '.json'),
            ContentType='application/json',
        )
        notify(config, certconfig, build_key(config.prefix, domain + '.json'))

def load_cert(config, tmp: str) -> None:
    """upload the certificate files to Amazon S3"""
    bucket = s3.Bucket(config.bucket_name)
    domains = set(domain.strip().replace('*.', '', 1) for domain in config.domains.split(','))
    for domain in domains:
        obj = bucket.Object(build_key(config.prefix, domain + '.json'))
        certconfig = json.load(obj.get()['Body'])

        set_files(tmp, 'config-dir/accounts/', certconfig['config']['account'])
        set_files(tmp, 'config-dir/csr/', certconfig['config']['csr'])
        set_files(tmp, 'config-dir/keys/', certconfig['config']['keys'])
        set_renewal_config(tmp, domain, certconfig['config']['renewal'])

        archive = os.path.join(tmp, 'config-dir/archive/', domain)
        pathlib.Path(archive).mkdir(parents=True, exist_ok=True)
        cert = certconfig['cert']
        bucket.download_file(cert['cert'], os.path.join(archive, 'cert1.pem'))
        bucket.download_file(cert['chain'], os.path.join(archive, 'chain1.pem'))
        bucket.download_file(cert['fullchain'], os.path.join(archive, 'fullchain1.pem'))
        bucket.download_file(cert['privkey'], os.path.join(archive, 'privkey1.pem'))

        live = os.path.join(tmp, 'config-dir/live/', domain)
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
def notify(config, certconfig: Dict[str, Union[str, Dict[str, str]]], key: str) -> None:
    """notify via SNS topic"""
    if config.notification == '':
        return
    template = string.Template("""acme-cert-updater
the certification is updated.

- domain: $domain
- bucket: $bucket
- object key: $key
""")
    text_message = template.substitute(
        domain=str(certconfig['domain']),
        bucket=config.bucket_name,
        key=key,
    )
    json_message = json.dumps({
        'domain': certconfig['domain'],
        'bucket': config.bucket_name,
        'key': key,
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
    bucket = s3.Bucket(config.bucket_name)
    domains = config.domains.split(',')
    for domain in domains:
        domain = domain.strip().replace('*.', '', 1)
        obj = bucket.Object(build_key(config.prefix, domain + '.json'))
        try:
            obj.load()
        except ClientError:
            return True
    return False

def lambda_handler(event, context): # pylint: disable=unused-argument
    """entry point of AWS Lambda"""
    config = Config()
    if needs_init(config):
        certonly(config)
    else:
        renew(config)
    return {}

if __name__ == "__main__":
    lambda_handler({}, None)
