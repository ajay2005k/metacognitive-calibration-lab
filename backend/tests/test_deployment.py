"""Release safety checks; AWS calls are mocked, no infrastructure is created."""

import json
import subprocess
import pytest
from deploy.aws import update as release


def test_release_command_inputs_and_shell_syntax():
    with pytest.raises(ValueError):
        release.release_commands("valid-bucket-name", "main; rm -rf /", "us-east-1")
    with pytest.raises(ValueError):
        release.release_commands("bucket;evil", "a" * 40, "us-east-1")
    command = release.release_commands("valid-bucket-name", "a" * 40, "us-east-1")[0]
    result = subprocess.run(
        ["bash", "-n"], input=command, text=True, capture_output=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("terminal", ["Success", "Failed"])
def test_success_is_reported_only_after_ssm_success(monkeypatch, tmp_path, terminal):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(
        release.subprocess, "check_output", lambda *args, **kwargs: "a" * 40 + "\n"
    )
    monkeypatch.setattr(release.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(release.time, "sleep", lambda *args: None)
    statuses = iter(["InProgress", terminal])

    def aws(region, *args, **kwargs):
        if args[:2] == ("cloudformation", "describe-stacks"):
            return {
                "Stacks": [
                    {
                        "StackStatus": "CREATE_COMPLETE",
                        "Parameters": [
                            {
                                "ParameterKey": "ArtifactBucket",
                                "ParameterValue": "valid-bucket-name",
                            }
                        ],
                        "Outputs": [
                            {"OutputKey": "InstanceId", "OutputValue": "i-test"},
                            {
                                "OutputKey": "LiveUrl",
                                "OutputValue": "https://test.example",
                            },
                        ],
                    }
                ]
            }
        if args[:2] == ("ssm", "send-command"):
            p = args[args.index("--parameters") + 1]
            from pathlib import Path

            payload = json.loads(Path(p.removeprefix("file://")).read_text())
            assert payload["executionTimeout"] == ["1500"]
            return {"Command": {"CommandId": "command-test"}}
        if args[:2] == ("ssm", "get-command-invocation"):
            return {"Status": next(statuses)}
        return {}

    monkeypatch.setattr(release, "aws", aws)
    if terminal == "Failed":
        with pytest.raises(RuntimeError, match="Deployment Failed"):
            release.update("us-east-1", "mclab-prod")
        assert not summary.exists()
    else:
        assert release.update("us-east-1", "mclab-prod") == "https://test.example"
        assert "https://test.example" in summary.read_text()


def test_oidc_subject_matches_verified_github_immutable_identity():
    from deploy.aws.setup_github import subject_from_repository

    metadata = {
        "owner": {"login": "ajay2005k", "id": 91924588},
        "name": "metacognitive-calibration-lab",
        "id": 1428649326,
    }
    assert (
        subject_from_repository(metadata)
        == "repo:ajay2005k@91924588/metacognitive-calibration-lab@1428649326:ref:refs/heads/main"
    )
    assert (
        subject_from_repository(metadata, legacy=True)
        == "repo:ajay2005k/metacognitive-calibration-lab:ref:refs/heads/main"
    )
