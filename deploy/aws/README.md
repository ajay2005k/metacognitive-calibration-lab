# AWS deployment

This directory prepares an AWS deployment; a live URL exists only after a successful deployment and HTTPS health check. The deployment does not use the Sites hosting service.

## Architecture and access

- CloudFront supplies an AWS-hosted HTTPS domain (`https://…cloudfront.net`); no purchased domain is required. HTTP redirects to HTTPS.
- A CloudFront Function requires a generated shared username/password for all pages and APIs. This is a site access gate, not a new participant identity system. The username is `instructor`; share access only with the class. Anyone with this shared credential can use the instructor controls, including delete/export.
- Valid authentication is stripped at the edge before forwarding to the origin. Unauthorized requests receive 401 and are not cached.
- One Amazon Linux 2023 `t3.small` EC2 instance runs Caddy, Gunicorn/Flask, and MongoDB in Docker. Images are built from the exact Git commit uploaded to a private encrypted S3 bucket.
- No MongoDB, Flask, or SSH ports are exposed. The EC2 security group accepts port 80 only from AWS's CloudFront origin-facing managed prefix list. Caddy additionally verifies a random origin secret, preventing a different CloudFront distribution from accessing the origin.
- The browser-to-CloudFront leg uses HTTPS. CloudFront-to-EC2 traffic uses HTTP; the shared gateway credential is removed before that leg. For studies requiring TLS on every hop, provision an owned domain and an origin certificate before collecting data.
- MongoDB files live at `/var/lib/mclab/mongo` on the encrypted EC2 root EBS volume. They survive container restarts/reboots. The disk is retained on termination to avoid silent data deletion; replacing a server requires an explicit disk backup/restore or attachment workflow. This script intentionally refuses to update an existing stack.
- A stable Elastic IP, instance IMDSv2, private S3 access, and Session Manager support are configured. Source artifacts and class data are not public S3 objects.

## Connect AWS first

Attach an AWS identity through the execution environment's cloud credential settings. Credentials must be reported ready by the cloud environment. Do not paste access keys into chat or commit credentials. An AWS connection is separate from the GitHub connection.

The caller needs permission to inspect STS identity and EC2 networking/AMI/prefix lists; create/manage the named artifact bucket; and create/read CloudFormation stacks with EC2, IAM instance roles, and CloudFront resources. The deployment uses `CAPABILITY_IAM`. Use a teaching/sandbox AWS account and your normal IAM policy review. The instance role itself can read only its source artifact and use SSM; it does not inherit the deployer's permissions.

The CLI uses the configured identity/profile as provided by the runtime. In a multi-account cloud environment, select the intended AWS connection using its non-secret identity manifest, not guessed profile names. No login or replacement credential is attempted by the deployment script.

## Deploy

Prerequisites: AWS CLI, Python 3.11+, Git, an enabled commercial AWS region, available EC2/CloudFront quota, and a public subnet with an internet-gateway default route. The default VPC/subnets are discovered when available; a supplied subnet must have VPC DNS support and hostnames enabled. No VPC configuration is changed automatically.

Commit changes before running; only committed source is uploaded. From the repository root:

```bash
python deploy/aws/deploy.py --region us-east-1 --stack-name mclab-prod
```

To select an existing public subnet:

```bash
python deploy/aws/deploy.py --region us-east-1 --stack-name mclab-prod --subnet-id subnet-YOUR_SUBNET_ID
```

`us-east-1` is the documented default when no region is configured, not a claim about your account. Override it with `--region` or `AWS_REGION`. CloudFront may take 15–30 minutes. The script prints a live link only after CloudFormation reports completion and an authenticated `/api/health` request succeeds through HTTPS.

Generated login credentials and deployment metadata are stored with restrictive permissions in `.aws-deployment/<stack-name>/`, which is excluded from Git and Docker builds. The password is not printed in logs or committed. Read `credentials.json` privately to retrieve it. CloudFormation secret inputs use `NoEcho`; administrators who can inspect the CloudFront Function or instance configuration can access the shared gate credentials/secrets and should be treated as trusted deployment administrators.

The script creates a private artifact bucket named `mclab-artifacts-ACCOUNT-REGION`; it does not delete an existing bucket or alter unrelated application stacks. It refuses to replace an existing stack to protect its database host. If provisioning fails, inspect the stack events and SSM `/var/log/mclab-bootstrap.log`; a failed or pending stack is never reported as a live application.

## Costs and teardown

This deployment creates billable AWS resources: EC2 instance, 30 GiB gp3 EBS, public IPv4, S3 source artifacts, and CloudFront requests/data transfer. Prices depend on region and usage; no free-tier claim is made. Stop/delete resources when the class no longer needs the service. CloudFront is configured with `PriceClass_100`; caching is disabled to avoid caching participant/session data.

Before teardown, export the data and take an EBS snapshot or MongoDB backup. Then delete the named CloudFormation stack using AWS's console or CLI:

```bash
aws cloudformation delete-stack --region us-east-1 --stack-name mclab-prod
```

The root EBS disk is intentionally retained and continues to cost storage after instance deletion. The artifact bucket is created outside the stack and is also retained. Inspect tags/account/region and explicitly remove those artifacts and disks only after confirming the backup and that they are no longer needed. A new stack name creates a new empty database, not a migration.

## Local production-container check

```bash
ORIGIN_SECRET=local-verification-only docker compose -p mclab-production-check -f docker-compose.production.yml up -d --build
curl -H 'X-Origin-Verify: local-verification-only' http://127.0.0.1:8080/api/health
```

A request without the origin header returns 403. This local check bypasses CloudFront and therefore tests the origin, not an AWS live deployment. Set `MONGO_DATA_DIR` to use a specific data directory; otherwise a Compose-managed volume is used. Never use production credentials as the local example value.

Regenerate `cloudformation.json` after editing `template.py`:

```bash
python deploy/aws/template.py
```

CloudFormation validation and actual AWS deployment still require a connected account. Offline `cfn-lint` and local container tests can validate structure/runtime without provisioning resources.

## Automatic deployment on GitHub pushes (recommended connection)

You do not need to give AWS access keys, passwords, or your root login to ChatGPT or GitHub. Use GitHub Actions OIDC: GitHub requests a short-lived AWS session for this repository's `main` branch. The repository includes `.github/workflows/deploy.yml`.

### One-time AWS setup

Sign in to your own AWS account and open **AWS CloudShell** in the console. The initial setup creates billable hosting resources described above and a restricted GitHub release role. Use an account identity permitted to create those resources and the OIDC provider/role; this is a one-time owner action, not a permission granted to the CI role.

Paste these commands in CloudShell (use a fresh folder, or pull the latest source if it already exists):

```bash
git clone https://github.com/ajay2005k/metacognitive-calibration-lab.git mclab-aws
cd mclab-aws
python3 deploy/aws/setup_github.py --region us-east-1
```

This creates the hosting stack if it is absent; first provisioning can take 15–30 minutes. Keep CloudShell open and monitor its output. If an existing stack is still creating, wait for it to finish and rerun the setup script. An existing failed stack must be inspected/repaired rather than overwritten.

The script reuses an existing GitHub OIDC provider when its audience is compatible. It creates/updates only the project's tagged release role, trusting exactly `repo:ajay2005k@91924588/metacognitive-calibration-lab@1428649326:ref:refs/heads/main` and audience `sts.amazonaws.com`. It will not overwrite an unrelated role with the same name.

At the end it prints the live site URL and three **non-secret** GitHub repository variables:

- `AWS_ROLE_ARN`: the generated role ARN. This is an identifier and is safe to share for connection setup.
- `AWS_REGION`: your selected region, default `us-east-1`.
- `AWS_STACK_NAME`: default `mclab-prod`.

Add these in the GitHub repository: **Settings → Secrets and variables → Actions → Variables → New repository variable**. There are no `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` repository secrets to create. The site login password stays in the private `.aws-deployment` directory in your CloudShell checkout; do not send that file to ChatGPT or commit it.

If your hosting stack was created from an older template that only let the EC2 role read one original source object, its `ReadSourceArtifact` policy must be upgraded to read this same bucket's `releases/*` prefix before enabling updates. The current template already does this. Never replace the database host just to change an IAM policy.

### What happens on each push

1. Push code to `main` (or manually run the workflow from GitHub's Actions tab).
2. GitHub runs backend tests, frontend tests, and the frontend production build. Failed checks prevent deployment.
3. If `AWS_ROLE_ARN` is configured, GitHub assumes the restricted release role using OIDC. This repository now includes its configured non-secret role default. In a new copy, remove that default until you have configured your own connection.
4. The exact tested Git commit is archived to the app's private S3 `releases/` prefix.
5. SSM executes the release on this app's existing EC2 instance. There is no SSH key or open SSH port.
6. The server locks releases against overlap, builds the images before replacing containers, and uses the fixed `mclab` Compose project and `/var/lib/mclab/mongo` data path. MongoDB is never taken down with `--volumes` by this workflow.
7. The job waits for container health and verifies the origin API before marking success. The Actions summary links to the existing HTTPS site. Release status is recorded on the server in `/opt/mclab/current-release` only after health succeeds.

The live URL remains the same. CloudFront caching is disabled, so no invalidation is needed for app updates. Updates normally take a few minutes, not literally instant. This is a single-server release and can cause a brief restart; it is not a zero-downtime rolling deployment. Keep regular database backups.

The release role can upload only to this app's release prefix, describe only its hosting stack, and send commands only to its instance using `AWS-RunShellScript`. It cannot create infrastructure, change IAM policies, or access other EC2 instances. SSM's command-invocation read action requires a wildcard resource because AWS does not expose resource-level scoping for that action. People permitted to push executable code to `main` are trusted deployment administrators of the app.

Hosting infrastructure changes still require an owner-reviewed CloudFormation update; the workflow deploys application code, not arbitrary changes to the stack. If the instance is replaced manually, rerun the connection setup so the role targets the new instance. A failed release is shown as failed; rollback is not automatic. To restore previous application code, revert the relevant commit and push the revert to `main`, after checking any data/schema implications.

### Connection for this repository

The owner created the AWS connection in account `014679146311`, region `us-east-1`, stack `mclab-prod`. The workflow uses the non-secret role ARN `arn:aws:iam::014679146311:role/mclab-prod-github-deploy` as its default, because the connected GitHub integration cannot write Actions variables. Repository variables can still override the defaults. No AWS access keys are stored in the workflow. Push-to-main deployment is enabled for this repository once that workflow change is pushed.

Owner-provided site: https://d1enzhyo49eo40.cloudfront.net. The shared site login remains required; its password stays in the owner's private CloudShell deployment files.

### Repair the original name-only OIDC trust

The verified GitHub token for this repository includes immutable owner/repository IDs. The initial setup helper incorrectly used the older name-only subject; this rejected AWS sign-in even though hosting was healthy. The corrected helper resolves public GitHub repository metadata and trusts exactly the verified immutable identity on `main`, without a wildcard. Run once in your existing CloudShell checkout:

```bash
cd ~/mclab-aws
git pull --ff-only
python3 deploy/aws/setup_github.py --region us-east-1
```

For an already complete hosting stack this updates only the connection role; it does not replace the instance, reset the site password, or delete MongoDB data. Then rerun the GitHub workflow. `--legacy-subject` is available only for older repositories whose actual diagnostic token still uses name-only subjects. Custom subjects must be reviewed against actual GitHub identity claims.
