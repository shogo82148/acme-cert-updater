import os
import boto3
import os.path
import pathlib
import json
import logging
import tempfile
import certbot.main
import configobj
from datetime import datetime

# set up the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Config(object):
    @property
    def domains(self):
        return os.environ.get('UPDATER_DOMAINS')
    
    @property
    def email(self) -> str:
        return os.environ.get('UPDATER_EMAIL')
    
    @property
    def bucket_name(self) -> str:
        return os.environ.get('UPDATER_BUCKET_NAME')

    @property
    def prefix(self) -> str:
        return os.environ.get('UPDATER_PREFIX')

    @property
    def environment(self) -> str:
        return os.environ.get('UPDATER_ENVIRONMENT')

    @property
    def acme_server(self) -> str:
        return os.environ.get('UPDATER_ACME_SERVER', 'https://acme-v02.api.letsencrypt.org/directory')

def certonly(config):
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

def renew(config):
    with tempfile.TemporaryDirectory() as tmp:
        load_cert(config, tmp)
        input_array = [
            'renew',
            '--config-dir', os.path.join(tmp, 'config-dir/'),
            '--work-dir', os.path.join(tmp, 'word-dir/'),
            '--logs-dir', os.path.join(tmp, 'logs-dir/'),
        ]
        certbot.main.main(input_array)
        # save_cert(config, tmp)

s3 = boto3.resource('s3')
def save_cert(config, tmp):
    """upload the certificate files to Amazon S3"""
    bucket = s3.Bucket(config.bucket_name)
    domains = config.domains.split(',')
    now = datetime.utcnow().isoformat()
    for domain in domains:
        domain = domain.strip().replace('*.', '', 1)
        live = os.path.join(tmp, 'config-dir/live/', domain)
        bucket.upload_file(os.path.join(live, 'cert.pem'), build_key(config.prefix, domain, now, 'cert.pem'))
        bucket.upload_file(os.path.join(live, 'chain.pem'), build_key(config.prefix, domain, now, 'chain.pem'))
        bucket.upload_file(os.path.join(live, 'fullchain.pem'), build_key(config.prefix, domain, now, 'fullchain.pem'))
        bucket.upload_file(os.path.join(live, 'privkey.pem'), build_key(config.prefix, domain, now, 'privkey.pem'))

        certconfig = {
            'timestamp': now,
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
            Body = json.dumps(certconfig),
            Key = build_key(config.prefix, domain + '.json'),
            ContentType = 'application/json',
        )

def load_cert(config, tmp):
    """upload the certificate files to Amazon S3"""
    bucket = s3.Bucket(config.bucket_name)
    domains = config.domains.split(',')
    for domain in domains:
        domain = domain.strip().replace('*.', '', 1)
        obj = bucket.Object(build_key(config.prefix, domain + '.json'))
        certconfig = json.load(obj.get()['Body'])

        set_files(tmp, 'config-dir/accounts/', certconfig['config']['account'])
        set_files(tmp, 'config-dir/csr/', certconfig['config']['csr'])
        set_files(tmp, 'config-dir/keys/', certconfig['config']['keys'])
        set_renewal_config(tmp, domain, certconfig['config']['renewal'])

        archive = os.path.join(tmp, 'config-dir/archive/', domain)
        pathlib.Path(archive).mkdir(parents = True, exist_ok = True)
        live = os.path.join(tmp, 'config-dir/live/', domain)
        pathlib.Path(live).mkdir(parents = True, exist_ok = True)
        bucket.download_file(certconfig['cert']['cert'], os.path.join(archive, 'cert1.pem'))
        bucket.download_file(certconfig['cert']['chain'], os.path.join(archive, 'chain1.pem'))
        bucket.download_file(certconfig['cert']['fullchain'], os.path.join(archive, 'fullchain1.pem'))
        bucket.download_file(certconfig['cert']['privkey'], os.path.join(archive, 'privkey1.pem'))
        os.symlink(os.path.join(archive, 'cert1.pem'), os.path.join(live, 'cert.pem'))
        os.symlink(os.path.join(archive, 'chain1.pem'), os.path.join(live, 'chain.pem'))
        os.symlink(os.path.join(archive, 'fullchain1.pem'), os.path.join(live, 'fullchain.pem'))
        os.symlink(os.path.join(archive, 'privkey1.pem'), os.path.join(live, 'privkey.pem'))

def get_files(tmp, subdir):
    config = {}
    path = pathlib.Path(tmp, subdir)
    for root, _, files in os.walk(str(path)):
        for name in files:
            filepath = pathlib.Path(root, name)
            config[str(filepath.relative_to(path))] = filepath.read_text()
    return config

def set_files(tmp, subdir, config):
    path = pathlib.Path(tmp, subdir)
    for key, value in config.items():
        filepath = path.joinpath(key)
        filepath.parent.mkdir(parents = True, exist_ok = True)
        filepath.write_text(value)

def get_renewal_config(tmp, domain):
    config = {}
    tmppath = pathlib.Path(tmp)
    cfg = configobj.ConfigObj(os.path.join(tmp, 'config-dir', 'renewal', domain + '.conf'))
    for key in ['archive_dir', 'cert', 'privkey', 'chain', 'fullchain']:
        cfg[key] = str(pathlib.Path(cfg[key]).relative_to(tmppath))
    for key in ['config_dir', 'work_dir', 'logs_dir']:
        cfg['renewalparams'][key] = str(pathlib.Path(cfg['renewalparams'][key]).relative_to(tmppath))
    for key, value in cfg.items():
        config[key] = value
    return config

def set_renewal_config(tmp, domain, config):
    tmppath = pathlib.Path(tmp)
    for key in ['archive_dir', 'cert', 'privkey', 'chain', 'fullchain']:
        config[key] = str(pathlib.Path(tmppath / config[key]))
    for key in ['config_dir', 'work_dir', 'logs_dir']:
        config['renewalparams'][key] = str(pathlib.Path(tmppath / config['renewalparams'][key]))

    ret = configobj.ConfigObj()
    conf_path = pathlib.Path(tmp, 'config-dir', 'renewal', domain + '.conf')
    conf_path.parent.mkdir(parents = True, exist_ok = True)
    ret.filename = str(conf_path)
    for key, value in config.items():
        ret[key] = value
    ret.write()


def build_key(*segment) -> str:
    path = "/".join(segment)
    path = path.replace("//", "/")
    if len(path) > 1 and path[0] == "/":
        path = path[1:]
    return path

def lambda_handler(event, context):
    return {}

if __name__ == "__main__":
    lambda_handler({}, None)
