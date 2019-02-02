import json
import os
import logging

# set up the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# load settings
domains = os.environ.get('UPDATER_DOMAINS')
email = os.environ.get('UPDATER_EMAIL')
bucket_name = os.environ.get('UPDATER_BUCKET_NAME')
prefix = os.environ.get('UPDATER_PREFIX')
environment = os.environ.get('UPDATER_ENVIRONMENT')
acme_server = os.environ.get('UPDATER_ACME_SERVER', 'https://acme-v02.api.letsencrypt.org/directory')

def lambda_handler(event, context):
    return {}
