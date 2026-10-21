"""Create a first AWS deployment using the caller's configured AWS CLI identity."""

import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def aws(region, *args, allow_error=False):
    result = subprocess.run(
        ["aws", "--region", region, *args, "--output", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        if allow_error:
            return None
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip() else {}


def private_json(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(value, output)


def deploy(region, name, subnet_id=None):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,39}", name):
        raise RuntimeError(
            "Stack name must begin with a letter and contain at most 40 letters, digits, or hyphens."
        )
    if not shutil.which("aws"):
        raise RuntimeError(
            "Install AWS CLI and connect an AWS identity in the environment cloud settings first."
        )
    if subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).strip():
        raise RuntimeError(
            "Commit the source before deploying; only committed source is uploaded."
        )
    identity = aws(region, "sts", "get-caller-identity")
    state = ROOT / ".aws-deployment" / name
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state, 0o700)
    existing = aws(
        region,
        "cloudformation",
        "describe-stacks",
        "--stack-name",
        name,
        allow_error=True,
    )
    if existing:
        raise RuntimeError(
            "This stack already exists. Inspect it before updating; this script creates new stacks only to avoid replacing a database host."
        )
    if subnet_id:
        subnets = aws(region, "ec2", "describe-subnets", "--subnet-ids", subnet_id)[
            "Subnets"
        ]
    else:
        subnets = aws(
            region,
            "ec2",
            "describe-subnets",
            "--filters",
            "Name=default-for-az,Values=true",
        )["Subnets"]
    if not subnets:
        raise RuntimeError(
            "No default public subnet found. Supply --subnet-id for an internet-routed subnet."
        )
    subnet = sorted(subnets, key=lambda s: s["SubnetId"])[0]
    vpc = subnet["VpcId"]
    for attribute in ("enableDnsSupport", "enableDnsHostnames"):
        result = aws(
            region,
            "ec2",
            "describe-vpc-attribute",
            "--vpc-id",
            vpc,
            "--attribute",
            attribute,
        )
        if not result[attribute[0].upper() + attribute[1:]]["Value"]:
            raise RuntimeError(
                f"{vpc} must have {attribute} enabled; no VPC settings were changed."
            )
    routes = aws(
        region, "ec2", "describe-route-tables", "--filters", f"Name=vpc-id,Values={vpc}"
    )["RouteTables"]
    explicit = [
        r
        for r in routes
        if any(a.get("SubnetId") == subnet["SubnetId"] for a in r["Associations"])
    ]
    effective = explicit or [
        r for r in routes if any(a.get("Main") for a in r["Associations"])
    ]
    if not any(
        r.get("DestinationCidrBlock") == "0.0.0.0/0"
        and r.get("GatewayId", "").startswith("igw-")
        for table in effective
        for r in table["Routes"]
    ):
        raise RuntimeError(
            "Selected subnet needs a default internet-gateway route; no networking was changed."
        )
    prefix_lists = aws(
        region,
        "ec2",
        "describe-managed-prefix-lists",
        "--filters",
        "Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing",
    )["PrefixLists"]
    if not prefix_lists:
        raise RuntimeError(
            "AWS CloudFront origin-facing managed prefix list is unavailable in this region."
        )
    bucket = f"mclab-artifacts-{identity['Account']}-{region}"
    if (
        aws(region, "s3api", "head-bucket", "--bucket", bucket, allow_error=True)
        is None
    ):
        args = ["s3api", "create-bucket", "--bucket", bucket]
        if region != "us-east-1":
            args += ["--create-bucket-configuration", f"LocationConstraint={region}"]
        aws(region, *args)
    aws(
        region,
        "s3api",
        "put-public-access-block",
        "--bucket",
        bucket,
        "--public-access-block-configuration",
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true",
    )
    aws(
        region,
        "s3api",
        "put-bucket-encryption",
        "--bucket",
        bucket,
        "--server-side-encryption-configuration",
        json.dumps(
            {
                "Rules": [
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            }
        ),
    )
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    archive = state / "source.zip"
    subprocess.run(
        ["git", "archive", "--format=zip", "-o", str(archive), sha],
        cwd=ROOT,
        check=True,
    )
    key = f"releases/{sha}.zip"
    aws(
        region,
        "s3api",
        "put-object",
        "--bucket",
        bucket,
        "--key",
        key,
        "--body",
        str(archive),
    )
    password = secrets.token_urlsafe(24)
    authorization = (
        "Basic " + base64.b64encode(f"instructor:{password}".encode()).decode()
    )
    credentials = {
        "username": "instructor",
        "password": password,
        "region": region,
        "stack": name,
    }
    private_json(state / "credentials.json", credentials)
    values = {
        "ArtifactBucket": bucket,
        "ArtifactKey": key,
        "VpcId": vpc,
        "SubnetId": subnet["SubnetId"],
        "CloudFrontPrefixListId": prefix_lists[0]["PrefixListId"],
        "OriginSecret": secrets.token_urlsafe(40),
        "AuthHeader": authorization,
    }
    params = state / "parameters.json"
    private_json(
        params, [{"ParameterKey": k, "ParameterValue": v} for k, v in values.items()]
    )
    try:
        aws(
            region,
            "cloudformation",
            "validate-template",
            "--template-body",
            f"file://{ROOT / 'deploy/aws/cloudformation.json'}",
        )
        created = aws(
            region,
            "cloudformation",
            "create-stack",
            "--stack-name",
            name,
            "--template-body",
            f"file://{ROOT / 'deploy/aws/cloudformation.json'}",
            "--parameters",
            f"file://{params}",
            "--capabilities",
            "CAPABILITY_IAM",
            "--tags",
            "Key=Project,Value=MCLab",
        )
    finally:
        params.unlink(missing_ok=True)
    private_json(
        state / "deployment.json",
        dict(created, region=region, artifact_bucket=bucket, commit=sha),
    )
    print(
        f"Creating {name} in {region}. CloudFront can take 15–30 minutes. Credentials saved privately to {state / 'credentials.json'}.",
        flush=True,
    )
    for _ in range(120):
        stack = aws(
            region,
            "cloudformation",
            "describe-stacks",
            "--stack-name",
            created["StackId"],
        )["Stacks"][0]
        status = stack["StackStatus"]
        if status == "CREATE_COMPLETE":
            break
        if status != "CREATE_IN_PROGRESS":
            raise RuntimeError(
                f"Stack status: {status}. Inspect CloudFormation events; no live URL is confirmed."
            )
        time.sleep(20)
    else:
        raise RuntimeError(
            "Stack still creating. Inspect CloudFormation; no live URL is confirmed yet."
        )
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
    url = outputs["LiveUrl"]
    for _ in range(60):
        try:
            request = urllib.request.Request(
                url + "/api/health", headers={"Authorization": authorization}
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                if json.load(response).get("status") == "ok":
                    private_json(
                        state / "deployment.json",
                        dict(
                            created,
                            region=region,
                            artifact_bucket=bucket,
                            commit=sha,
                            **outputs,
                        ),
                    )
                    print(f"Verified live HTTPS endpoint: {url}")
                    print(
                        f"Username: instructor. Password is in {state / 'credentials.json'}; it is not written to logs."
                    )
                    return
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            pass
        time.sleep(10)
    raise RuntimeError(
        "Infrastructure exists, but HTTPS application health did not pass. Inspect SSM and /var/log/mclab-bootstrap.log."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or "us-east-1",
    )
    parser.add_argument("--stack-name", default="mclab-prod")
    parser.add_argument("--subnet-id")
    args = parser.parse_args()
    try:
        deploy(args.region, args.stack_name, args.subnet_id)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
