"""One-time setup in AWS CloudShell. No access keys are sent to GitHub or chat."""

import argparse
import json
import re
import tempfile
from pathlib import Path

try:
    from .deploy import aws, deploy, private_json
except ImportError:
    from deploy import aws, deploy, private_json


def connect(region, stack_name, repository):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Expected owner/repository")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,39}", stack_name):
        raise ValueError("Invalid stack name")
    identity = aws(region, "sts", "get-caller-identity")
    account = identity["Account"]
    partition = identity["Arn"].split(":")[1]
    existing = aws(
        region,
        "cloudformation",
        "describe-stacks",
        "--stack-name",
        stack_name,
        allow_error=True,
    )
    if not existing:
        deploy(region, stack_name)
    stack = aws(
        region, "cloudformation", "describe-stacks", "--stack-name", stack_name
    )["Stacks"][0]
    if stack["StackStatus"] not in (
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
    ):
        raise RuntimeError(
            "Finish or repair the hosting stack before configuring automatic releases"
        )
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
    params = {p["ParameterKey"]: p.get("ParameterValue") for p in stack["Parameters"]}
    provider_arn = f"arn:{partition}:iam::{account}:oidc-provider/token.actions.githubusercontent.com"
    provider = aws(
        region,
        "iam",
        "get-open-id-connect-provider",
        "--open-id-connect-provider-arn",
        provider_arn,
        allow_error=True,
    )
    if provider is None:
        provider_arn = aws(
            region,
            "iam",
            "create-open-id-connect-provider",
            "--url",
            "https://token.actions.githubusercontent.com",
            "--client-id-list",
            "sts.amazonaws.com",
        )["OpenIDConnectProviderArn"]
    elif "sts.amazonaws.com" not in provider["ClientIDList"]:
        raise RuntimeError(
            "Existing GitHub OIDC provider does not allow sts.amazonaws.com. Ask its owner to review that audience."
        )
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Federated": provider_arn},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                        "token.actions.githubusercontent.com:sub": f"repo:{repository}:ref:refs/heads/main",
                    }
                },
            }
        ],
    }
    bucket = params["ArtifactBucket"]
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "cloudformation:DescribeStacks",
                "Resource": stack["StackId"],
            },
            {
                "Effect": "Allow",
                "Action": "s3:PutObject",
                "Resource": f"arn:{partition}:s3:::{bucket}/releases/*",
            },
            {
                "Effect": "Allow",
                "Action": "ssm:SendCommand",
                "Resource": [
                    f"arn:{partition}:ec2:{region}:{account}:instance/{outputs['InstanceId']}",
                    f"arn:{partition}:ssm:{region}::document/AWS-RunShellScript",
                ],
            },
            {"Effect": "Allow", "Action": "ssm:GetCommandInvocation", "Resource": "*"},
        ],
    }
    role_name = f"{stack_name}-github-deploy"
    existing_role = aws(
        region, "iam", "get-role", "--role-name", role_name, allow_error=True
    )
    with tempfile.TemporaryDirectory(prefix="mclab-oidc-") as directory:
        trust_file, policy_file = (
            Path(directory) / "trust.json",
            Path(directory) / "policy.json",
        )
        private_json(trust_file, trust)
        private_json(policy_file, policy)
        if existing_role:
            tags = {t["Key"]: t["Value"] for t in existing_role["Role"].get("Tags", [])}
            if tags.get("Project") != "MCLab" or tags.get("Repository") != repository:
                raise RuntimeError(
                    "A different role already uses this name; no existing role was modified"
                )
            aws(
                region,
                "iam",
                "update-assume-role-policy",
                "--role-name",
                role_name,
                "--policy-document",
                f"file://{trust_file}",
            )
            role = existing_role["Role"]
        else:
            role = aws(
                region,
                "iam",
                "create-role",
                "--role-name",
                role_name,
                "--assume-role-policy-document",
                f"file://{trust_file}",
                "--max-session-duration",
                "3600",
                "--tags",
                "Key=Project,Value=MCLab",
                f"Key=Repository,Value={repository}",
            )["Role"]
        aws(
            region,
            "iam",
            "put-role-policy",
            "--role-name",
            role_name,
            "--policy-name",
            "ReleaseThisLaboratory",
            "--policy-document",
            f"file://{policy_file}",
        )
    print(
        "\nGitHub connection prepared. Add these repository Actions VARIABLES (not secrets):"
    )
    print(
        json.dumps(
            {
                "AWS_ROLE_ARN": role["Arn"],
                "AWS_REGION": region,
                "AWS_STACK_NAME": stack_name,
            },
            indent=2,
        )
    )
    print(f"\nLive site: {outputs['LiveUrl']}")
    print(
        "The role ARN is safe to share. Do not share credentials.json or any access keys."
    )
    print(
        "If this was a first deployment, the site password is in the private .aws-deployment folder in this checkout."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--stack-name", default="mclab-prod")
    parser.add_argument(
        "--repository", default="ajay2005k/metacognitive-calibration-lab"
    )
    args = parser.parse_args()
    connect(args.region, args.stack_name, args.repository)
