# acme-cert-updater

[![Build Status](https://travis-ci.com/shogo82148/acme-cert-updater.svg?branch=master)](https://travis-ci.com/shogo82148/acme-cert-updater)

The acme-cert-updater automatically updates the certificate using ACME (Automated Certificate Management Environment) and Amazon Route 53.
It is a pre-build AWS Serverless Application of [Certbot](https://certbot.eff.org/) with [certbot-dns-route53](https://certbot-dns-route53.readthedocs.io/en/stable/) plugin.

## Usage

### Permission

The acme-cert-updater requires some SAM policy templates (S3ReadPolicy, S3CrudPolicy, and SNSPublishMessagePolicy),
and CAPABILITY_IAM Capabilities to use the Amazon Web Services Route 53 API.

### Deploy

The acme-cert-updater is available on [AWS Serverless Application Repository](https://serverlessrepo.aws.amazon.com/applications/arn:aws:serverlessrepo:us-east-1:445285296882:applications~acme-cert-updater).

Or here is a resource template of AWS Serverless Application Model.

```yaml
AWSTemplateFormatVersion: 2010-09-09
Transform: AWS::Serverless-2016-10-31

Resources:
  AcmeCertUpdater:
    Type: AWS::Serverless::Application
    Properties:
      Location:
        ApplicationId: arn:aws:serverlessrepo:us-east-1:445285296882:applications/acme-cert-updater
        SemanticVersion: 0.0.14
      Parameters: 
        # url for acme server
        # AcmeServer: https://acme-v02.api.letsencrypt.org/directory # Uncomment to override default value
        # S3 bucket name for saving the certificates
        BucketName: YOUR_BUCKET_NAME
        # Comma separated list of domains to update the certificates
        Domains: YOUR_DOMAINS
        # Email address
        Email: YOUR_EMAIL_ADDRESS
        # execution environment
        # Environment: production # Uncomment to override default value
        # Amazon Route 53 Hosted Zone ID
        HostedZone: YOUR_HOSTED_ZONE_ID
        # The Amazon SNS topic Amazon Resource Name (ARN) to which the updater reports events.
        Notification: ARN_SNS_TOPIC
        # Prefix of objects on S3 bucket
        # Prefix: ""  # Uncomment to override default value
```

The following command will create a Cloudformation Stack and deploy the SAM resources.

```
aws cloudformation \
    --template-file template.yaml \
    --stack-name <STACK_NAME> \
    --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_IAM
```

### Download the certificate

[download-certificate.sh](https://github.com/shogo82148/acme-cert-updater/blob/master/download-certificate.sh) is a helper script for downloading the certificate.
It downloads the certificate, and executes the given command if the certficate is renewal.
Here is an example for reloading nginx.

```
./download-certificate.sh bucket-name example.com.json /etc/ssl/example.com systemctl reload nginx
```

bash, [AWS CLI](https://aws.amazon.com/cli/), and [jq](https://stedolan.github.io/jq/) are required.

## LICENSE

MIT License Copyright (c) 2019 Ichinose Shogo
