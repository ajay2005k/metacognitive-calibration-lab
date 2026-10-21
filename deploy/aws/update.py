"""Release a tested Git commit to the existing EC2 host using SSM, not SSH."""

import os
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

try:
    from .deploy import ROOT, aws, private_json
except ImportError:
    from deploy import ROOT, aws, private_json


def release_commands(bucket, sha, region):
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("Expected a complete Git commit SHA")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise ValueError("Invalid artifact bucket")
    q = shlex.quote
    release = f"/opt/mclab/releases/{sha}"
    compose = f"docker compose -p mclab --env-file /opt/mclab/.env.production -f {q(release)}/docker-compose.production.yml"
    return [
        f"""set -eu
exec 9>/var/lock/mclab-deploy.lock
flock -w 1200 9
mkdir -p {q(release)}
aws s3 cp {q(f"s3://{bucket}/releases/{sha}.zip")} /tmp/mclab-release-{sha}.zip --region {q(region)}
unzip -qo /tmp/mclab-release-{sha}.zip -d {q(release)}
cd {q(release)}
{compose} build
{compose} up -d --no-build --wait --wait-timeout 180
set -a
. /opt/mclab/.env.production
set +a
curl --fail --silent --show-error --retry 15 --retry-delay 2 --retry-all-errors --max-time 10 -H "X-Origin-Verify: $ORIGIN_SECRET" http://127.0.0.1/api/health
printf '%s\\n' {q(sha)} > /opt/mclab/current-release
rm -f /tmp/mclab-release-{sha}.zip
"""
    ]


def update(region, stack_name):
    stack = aws(
        region, "cloudformation", "describe-stacks", "--stack-name", stack_name
    )["Stacks"][0]
    if stack["StackStatus"] not in (
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
    ):
        raise RuntimeError("Hosting stack is not ready for an application update")
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}
    parameters = {
        p["ParameterKey"]: p.get("ParameterValue") for p in stack["Parameters"]
    }
    bucket = parameters["ArtifactBucket"]
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    with tempfile.TemporaryDirectory(prefix="mclab-release-") as directory:
        archive = Path(directory) / "source.zip"
        subprocess.run(
            ["git", "archive", "--format=zip", "-o", str(archive), sha],
            cwd=ROOT,
            check=True,
        )
        aws(
            region,
            "s3api",
            "put-object",
            "--bucket",
            bucket,
            "--key",
            f"releases/{sha}.zip",
            "--body",
            str(archive),
        )
        commands = Path(directory) / "command.json"
        private_json(
            commands,
            {
                "commands": release_commands(bucket, sha, region),
                "executionTimeout": ["1500"],
            },
        )
        command = aws(
            region,
            "ssm",
            "send-command",
            "--instance-ids",
            outputs["InstanceId"],
            "--document-name",
            "AWS-RunShellScript",
            "--timeout-seconds",
            "120",
            "--parameters",
            f"file://{commands}",
        )["Command"]
    print(f"Deploying {sha[:7]} through SSM command {command['CommandId']}", flush=True)
    for attempt in range(300):
        result = aws(
            region,
            "ssm",
            "get-command-invocation",
            "--command-id",
            command["CommandId"],
            "--instance-id",
            outputs["InstanceId"],
            allow_error=True,
        )
        if result and result["Status"] == "Success":
            url = outputs["LiveUrl"]
            print(f"Origin health verified; release completed: {url}")
            summary = os.getenv("GITHUB_STEP_SUMMARY")
            if summary:
                with open(summary, "a") as output:
                    output.write(
                        f"### MCLab release\n\nCommit: `{sha}`\n\nSite: {url}\n\nOrigin health passed. The shared site login is still required.\n"
                    )
            return url
        if result and result["Status"] not in ("Pending", "InProgress", "Delayed"):
            # Do not echo arbitrary remote output: it may contain application secrets.
            raise RuntimeError(
                f"Deployment {result['Status']}. Inspect command {command['CommandId']} in AWS Systems Manager."
            )
        if attempt % 6 == 0:
            print(
                f"Waiting for deployment: {result['Status'] if result else 'SSM delivery'}",
                flush=True,
            )
        time.sleep(5)
    raise RuntimeError("Deployment timed out; check Systems Manager before retrying")


if __name__ == "__main__":
    update(
        os.getenv("AWS_REGION", "us-east-1"),
        os.getenv("MCLAB_STACK_NAME", "mclab-prod"),
    )
