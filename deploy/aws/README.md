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
