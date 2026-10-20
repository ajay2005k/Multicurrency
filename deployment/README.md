# Deploy Sentinel from AWS CloudShell

This package is built for AWS Lambda Python 3.12 / Linux x86_64 and includes the compiled frontend, Lambda dependencies, deployment script, CloudFormation template, and faculty presentation guide. No laptop installation is required. The deployment script uses the AWS CLI already installed in CloudShell; it has no extra Python dependencies.

## Deploy

1. Sign in to the AWS Console. Select **Asia Pacific (Mumbai), ap-south-1**.
2. Open **CloudShell** using the terminal icon in the console header. Use a normal CloudShell environment with Internet access, not a VPC-only environment.
3. Choose **Actions → Upload file** and upload `sentinel-cloudshell.zip`.
4. Run:

```bash
unzip sentinel-cloudshell.zip && cd sentinel-cloudshell && python3 deploy.py --region ap-south-1
```

5. Choose a **workspace access key of at least 24 characters** when prompted, and confirm it. This is your application's shared access key, not an AWS access key. Input is hidden. Remember it; the script does not write it to the output file.
6. Wait for infrastructure provisioning and the public-site checks. CloudFront can take several minutes. The script prints **Deployment verified. Live website: https://…cloudfront.net** only after the public page, API, conversion, risk decisions, and DynamoDB history checks pass.
7. Open the printed URL in your laptop browser. Enter the workspace key on the sign-in page. You can now test and record the website without keeping any laptop terminal running.

The deployment uses your existing CloudShell AWS session. **No AWS access key, secret key, root credentials, or session token needs to be shared in chat.**

## What gets created

- Private, encrypted S3 frontend bucket and a CloudFront distribution with origin access control.
- API Gateway HTTP API and a Python Lambda function.
- Encrypted, pay-per-request DynamoDB table with point-in-time recovery.
- IAM execution role scoped to the table and logs.
- CloudWatch log group with 14-day retention.
- Private S3 bucket for deployment artifacts.

The frontend and `/api/*` share the CloudFront HTTPS domain. The API requires the workspace key; the health endpoint is public. The Lambda origin remains accessible through API Gateway, protected by that same key.

This creates **billable AWS resources**. Free-tier eligibility varies; do not assume the deployment is free. Set an AWS Budget alert, use synthetic data, and remove unused resources after grading. A small recording workload should use little request capacity, but storage, recovery, logging, and network charges still depend on usage and current pricing.

## Required AWS access

Your CloudShell role needs permission to create/manage the above resources: CloudFormation, S3, CloudFront, API Gateway v2, Lambda, DynamoDB, CloudWatch Logs, and IAM roles/policies/PassRole. AWS Academy or Learner Lab accounts may restrict IAM or CloudFront. An `AccessDenied` error needs the instructor/account administrator to adjust the lab permissions or approve a supported architecture. Do not bypass those restrictions or use root credentials.

If deployment fails, send the **error code and failed CloudFormation resource/event**, without credentials or your workspace access key. A failed stack may have created some resources; inspect its events before retrying.

## Optional: live exchange rates

Default deployment uses fixed **reference rates**, explicitly labeled in the UI. The public website will be live, but this does not make its currency data live.

To use real rates:

1. Obtain an ExchangeRate API v6 key.
2. In **Secrets Manager** in Mumbai, create a secret with **Other type of secret → Plaintext**. Store the raw API key as the plain-text secret value, not a JSON object. Do not put the provider key in the browser or in a Vite variable. Use the default AWS-managed Secrets Manager encryption key for this workflow.
3. Copy the secret ARN, which is a resource identifier rather than the key, and deploy/update with:

```bash
python3 deploy.py --region ap-south-1 --fx-provider exchangerate --fx-secret-arn YOUR_SECRET_ARN
```

The template gives Lambda permission to read that secret. The deployment identity also needs the IAM permissions required to create that policy. Secrets Manager adds charges; pricing and provider quotas apply. If an existing secret uses a customer-managed KMS key, additional decrypt permissions would be required; the supplied template uses the default AWS-managed key workflow.

## Updates and repeat runs

The default stack is `sentinel-payments`. Re-running the script updates that stack, refreshes frontend files, invalidates CloudFront's cache, and performs launch checks. Use the same workspace key if you want existing browser sessions to remain valid. Each run adds three synthetic **Launch verification** records. You may choose another stack name with `--stack`, using 3–24 lowercase letters/numbers/hyphens beginning with a letter.

The script deliberately refuses to update a failed/rolling-back stack. Inspect CloudFormation Events to resolve the failed resource first. `ROLLBACK_COMPLETE` stacks cannot be updated; after inspecting the failure and retained resources, remove the failed stack through CloudFormation before recreating it. Do not delete transaction data blindly.

## Clean up after grading

The stack has termination protection enabled. When you are finished:

1. Save any needed results. In CloudFormation, disable termination protection and delete the stack. Wait for deletion to complete; CloudFront removal can take time.
2. The frontend bucket and DynamoDB table are **retained** deliberately. Use the names in `deployment-output.json` to identify them, then delete them separately only if their data is no longer needed. Empty the S3 bucket before deletion.
3. Empty and delete the private deployment artifact bucket listed in `deployment-output.json`.
4. Delete any optional FX secret you created if no longer used.

Deleting the stack alone does not remove retained data or the artifact bucket. Confirm removal in the AWS Console to stop ongoing storage/recovery charges.

## Presenting to faculty

Read `FACULTY_DEMO.md` for a 4–5 minute recording script, reproducible payment scenarios, architecture diagram, and service-by-service explanation. The application currently uses rules in Lambda, **not Amazon Fraud Detector or a trained ML model**.
