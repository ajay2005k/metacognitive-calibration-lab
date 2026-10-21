"""Generate the standalone CloudFormation template (no SDK dependency)."""

import json
from pathlib import Path


def ref(name):
    return {"Ref": name}


def sub(text):
    return {"Fn::Sub": text}


def template():
    user_data = """#!/bin/bash
set -euo pipefail
exec > /var/log/mclab-bootstrap.log 2>&1
dnf install -y docker unzip
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins /opt/mclab /var/lib/mclab/mongo
curl -fsSL https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
curl -fsSL https://github.com/docker/buildx/releases/download/v0.28.0/buildx-v0.28.0.linux-amd64 -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-buildx
if ! command -v aws >/dev/null; then
    curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscli.zip
    unzip -q /tmp/awscli.zip -d /tmp
    /tmp/aws/install
fi
aws s3 cp s3://${ArtifactBucket}/${ArtifactKey} /tmp/mclab.zip --region ${AWS::Region}
unzip -q /tmp/mclab.zip -d /opt/mclab
cd /opt/mclab
umask 077
cat > .env.production <<'ENV'
ORIGIN_SECRET=${OriginSecret}
MONGO_DATA_DIR=/var/lib/mclab/mongo
WEB_BIND=0.0.0.0
WEB_PORT=80
ENV
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
"""
    resources = {
        "Role": {
            "Type": "AWS::IAM::Role",
            "Properties": {
                "AssumeRolePolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "ec2.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                },
                "ManagedPolicyArns": [
                    sub(
                        "arn:${AWS::Partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
                    )
                ],
                "Policies": [
                    {
                        "PolicyName": "ReadSourceArtifact",
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "s3:GetObject",
                                    "Resource": sub(
                                        "arn:${AWS::Partition}:s3:::${ArtifactBucket}/${ArtifactKey}"
                                    ),
                                }
                            ],
                        },
                    }
                ],
            },
        },
        "Profile": {
            "Type": "AWS::IAM::InstanceProfile",
            "Properties": {"Roles": [ref("Role")]},
        },
        "SecurityGroup": {
            "Type": "AWS::EC2::SecurityGroup",
            "Properties": {
                "GroupDescription": "CloudFront origin traffic only; no SSH, backend, or database ports",
                "VpcId": ref("VpcId"),
                "SecurityGroupIngress": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 80,
                        "ToPort": 80,
                        "SourcePrefixListId": ref("CloudFrontPrefixListId"),
                    }
                ],
            },
        },
        "Server": {
            "Type": "AWS::EC2::Instance",
            "Properties": {
                "ImageId": ref("ImageId"),
                "InstanceType": ref("InstanceType"),
                "IamInstanceProfile": ref("Profile"),
                "MetadataOptions": {
                    "HttpTokens": "required",
                    "HttpPutResponseHopLimit": 1,
                },
                "NetworkInterfaces": [
                    {
                        "DeviceIndex": "0",
                        "AssociatePublicIpAddress": True,
                        "SubnetId": ref("SubnetId"),
                        "GroupSet": [ref("SecurityGroup")],
                    }
                ],
                "BlockDeviceMappings": [
                    {
                        "DeviceName": "/dev/xvda",
                        "Ebs": {
                            "VolumeType": "gp3",
                            "VolumeSize": 30,
                            "Encrypted": True,
                            "DeleteOnTermination": False,
                        },
                    }
                ],
                "Tags": [{"Key": "Name", "Value": sub("${AWS::StackName}-server")}],
                "UserData": {"Fn::Base64": sub(user_data)},
            },
        },
        "AccessGate": {
            "Type": "AWS::CloudFront::Function",
            "Properties": {
                "Name": sub("${AWS::StackName}-access"),
                "AutoPublish": True,
                "FunctionConfig": {
                    "Comment": "Shared teaching-lab access gate; no participant identities",
                    "Runtime": "cloudfront-js-2.0",
                },
                "FunctionCode": sub("""function handler(event) {
  var request = event.request;
  var authorization = request.headers.authorization;
  if (!authorization || authorization.value !== '${AuthHeader}') {
    return {statusCode: 401, statusDescription: 'Unauthorized', headers: {
      'www-authenticate': {value: 'Basic realm="MCLab"'},
      'cache-control': {value: 'no-store'}
    }};
  }
  delete request.headers.authorization;
  return request;
}"""),
            },
        },
        "Distribution": {
            "Type": "AWS::CloudFront::Distribution",
            "Properties": {
                "DistributionConfig": {
                    "Enabled": True,
                    "Comment": sub("${AWS::StackName} teaching laboratory"),
                    "PriceClass": "PriceClass_100",
                    "HttpVersion": "http2",
                    "Origins": [
                        {
                            "Id": "mclab-server",
                            "DomainName": {"Fn::GetAtt": ["Server", "PublicDnsName"]},
                            "CustomOriginConfig": {
                                "HTTPPort": 80,
                                "OriginProtocolPolicy": "http-only",
                            },
                            "OriginCustomHeaders": [
                                {
                                    "HeaderName": "X-Origin-Verify",
                                    "HeaderValue": ref("OriginSecret"),
                                }
                            ],
                        }
                    ],
                    "DefaultCacheBehavior": {
                        "TargetOriginId": "mclab-server",
                        "ViewerProtocolPolicy": "redirect-to-https",
                        "AllowedMethods": [
                            "GET",
                            "HEAD",
                            "OPTIONS",
                            "PUT",
                            "PATCH",
                            "POST",
                            "DELETE",
                        ],
                        "CachedMethods": ["GET", "HEAD"],
                        "Compress": True,
                        "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                        "OriginRequestPolicyId": "b689b0a8-53d0-40ab-baf2-68738e2966ac",
                        "FunctionAssociations": [
                            {
                                "EventType": "viewer-request",
                                "FunctionARN": {
                                    "Fn::GetAtt": ["AccessGate", "FunctionARN"]
                                },
                            }
                        ],
                    },
                    "ViewerCertificate": {"CloudFrontDefaultCertificate": True},
                    "CustomErrorResponses": [
                        {"ErrorCode": code, "ErrorCachingMinTTL": 0}
                        for code in (400, 403, 404, 500, 502, 503, 504)
                    ],
                }
            },
        },
    }
    resources["PublicIp"] = {
        "Type": "AWS::EC2::EIP",
        "Properties": {"Domain": "vpc", "InstanceId": ref("Server")},
    }
    resources["Distribution"]["Properties"]["DistributionConfig"]["Origins"][0][
        "DomainName"
    ] = {
        "Fn::Join": [
            "",
            [
                "ec2-",
                {"Fn::Join": ["-", {"Fn::Split": [".", ref("PublicIp")]}]},
                {
                    "Fn::If": [
                        "UsEastOne",
                        ".compute-1.amazonaws.com",
                        sub(".${AWS::Region}.compute.amazonaws.com"),
                    ]
                },
            ],
        ]
    }
    return {
        "Conditions": {"UsEastOne": {"Fn::Equals": [ref("AWS::Region"), "us-east-1"]}},
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "MCLab: CloudFront HTTPS/access gate, EC2 Docker host, persistent encrypted MongoDB disk",
        "Parameters": {
            "ArtifactBucket": {"Type": "String"},
            "ArtifactKey": {"Type": "String"},
            "VpcId": {"Type": "AWS::EC2::VPC::Id"},
            "SubnetId": {"Type": "AWS::EC2::Subnet::Id"},
            "CloudFrontPrefixListId": {"Type": "String"},
            "ImageId": {
                "Type": "AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
                "Default": "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64",
            },
            "InstanceType": {
                "Type": "String",
                "Default": "t3.small",
                "AllowedValues": ["t3.small", "t3.medium"],
            },
            "OriginSecret": {
                "Type": "String",
                "NoEcho": True,
                "MinLength": 32,
                "AllowedPattern": "[A-Za-z0-9_-]+",
            },
            "AuthHeader": {
                "Type": "String",
                "NoEcho": True,
                "AllowedPattern": "Basic [A-Za-z0-9+/=]+",
            },
        },
        "Resources": resources,
        "Outputs": {
            "LiveUrl": {"Value": sub("https://${Distribution.DomainName}")},
            "InstanceId": {"Value": ref("Server")},
            "DistributionId": {"Value": ref("Distribution")},
        },
    }


if __name__ == "__main__":
    Path(__file__).with_name("cloudformation.json").write_text(
        json.dumps(template(), indent=2) + "\n"
    )
