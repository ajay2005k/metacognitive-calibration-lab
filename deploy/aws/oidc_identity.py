"""Print only non-secret identity claims to diagnose AWS role trust matching."""

import base64
import json
import os
import urllib.request


def identity():
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    url += ("&" if "?" in url else "?") + "audience=sts.amazonaws.com"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        token = json.load(response)["value"]
    encoded = token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    # Diagnostic decoding is not authentication; STS still verifies the signed token.
    safe = {
        k: claims.get(k)
        for k in (
            "iss",
            "aud",
            "sub",
            "repository",
            "repository_id",
            "ref",
            "job_workflow_ref",
        )
    }
    print(json.dumps(safe, indent=2))


if __name__ == "__main__":
    identity()
