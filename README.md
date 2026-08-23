# Cloud-Janitor Automation (v1.2)

An automated, serverless cloud governance tool designed to audit, detect, and clean up orphaned and idle infrastructure across cloud environments. Built with Python and Cloud SDKs, packaged with Docker, distributed via Docker Hub, and orchestrated serverlessly via AWS ECS Fargate and Amazon EventBridge.

---

## Architecture Overview

```
                          ┌───────────────────────────┐
                          │  Amazon EventBridge Rule  │
                          │   (Daily Cron Schedule)   │
                          └─────────────┬─────────────┘
                                        │ Triggers Task
                                        ▼
                          ┌───────────────────────────┐
                          │      AWS ECS Fargate      │
                          │ (Serverless Task Cluster) │
                          └─────────────┬─────────────┘
                                        │ Pulls Image
                                        ▼
                          ┌───────────────────────────┐
                          │     Docker Hub Registry   │
                          │ (cloud-janitor:latest)    │
                          └─────────────┬─────────────┘
                                        │ Assumes IAM Task Role
                                        ▼
                          ┌───────────────────────────┐
                          │    EC2 / Cloud SDK Scan   │
                          │  - Unattached EBS Volumes │
                          │  - Unassociated Elastic IP│
                          └──────┬─────────────┬──────┘
                                 │             │
                    Dry-Run Mode │             │ Live Mode (--force-delete)
                                 ▼             ▼
                   ┌─────────────────┐    ┌─────────────────┐
                   │ CloudWatch Logs │    │ Resource Purge  │
                   │ (Audit Trail)   │    │ (Cost Reduction)│
                   └─────────────────┘    └─────────────────┘
```

---

## Process Flow & Lifecycle

```
[ Trigger Event ] ──> [ Spin up Fargate Container ]
                              │
                              ▼
                   [ Assume IAM Role (No Keys) ]
                              │
                              ▼
                   [ Query Cloud SDK APIs ]
                   ├── Check status == 'available' (EBS)
                   └── Check associationId is None (EIP)
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
        [ Dry-Run (Default) ]     [ Enforcement Action ]
        • Log candidate ID        • ec2:DeleteVolume
        • Estimate saved cost     • ec2:ReleaseAddress
        • Zero state mutation     • Write audit to CloudWatch
                 │                         │
                 └────────────┬────────────┘
                              ▼
                 [ Container Terminates (0 Idle Cost) ]
```

---

## Repository Structure

```text
cloud-janitor/
├── Dockerfile                # Container runtime definition
├── requirements.txt          # Cloud SDK dependencies (boto3, botocore)
├── janitor.py                # Main governance scan & cleanup logic
├── task-definition.json      # AWS ECS Fargate Task Definition
├── eventbridge-target.json   # EventBridge automated target config
├── ecs-trust-policy.json     # IAM Service Trust Policy
├── janitor-policy.json       # Least-privilege IAM Actions
└── README.md                 # Project Documentation
```

---

## Implementation Steps & Commands

### 1. Local Testing with Docker

Build and test the container locally using safe dry-run flags:

```bash
# Build the Docker image
docker build -t cloud-janitor:1.2 .

# Test locally with credentials
docker run --rm \
  -e AWS_ACCESS_KEY_ID="<YOUR_ACCESS_KEY>" \
  -e AWS_SECRET_ACCESS_KEY="<YOUR_SECRET_KEY>" \
  -e AWS_REGION="eu-central-1" \
  cloud-janitor:1.2
```

### 2. Registry Distribution via Docker Hub

```bash
# Tag for release
docker tag cloud-janitor:1.2 <your-dockerhub-username>/cloud-janitor:latest

# Push to Docker Hub
docker push <your-dockerhub-username>/cloud-janitor:latest
```

### 3. Serverless Cloud Infrastructure Setup (AWS)

```bash
# Create CloudWatch Log Group
aws logs create-log-group --log-group-name /ecs/cloud-janitor --region eu-central-1

# Create ECS Cluster
aws ecs create-cluster --cluster-name cloud-governance-cluster --region eu-central-1

# Register Task Definition
aws ecs register-task-definition --cli-input-json file://task-definition.json --region eu-central-1

# Run On-Demand Task Scan
aws ecs run-task \
  --cluster cloud-governance-cluster \
  --task-definition cloud-janitor-task \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_ID>],securityGroups=[<SG_ID>],assignPublicIp=ENABLED}" \
  --region eu-central-1
```

### 4. Schedule Autonomous Execution (Amazon EventBridge)

```bash
# Create recurring schedule rule
aws events put-rule \
  --name "DailyCloudJanitorScan" \
  --schedule-expression "cron(0 0 * * ? *)" \
  --state ENABLED \
  --region eu-central-1

# Attach ECS Fargate as Target
aws events put-targets \
  --rule "DailyCloudJanitorScan" \
  --targets file://eventbridge-target.json \
  --region eu-central-1
```

---

## Core Functions Reference (`janitor.py`)

* `parse_args()`: Parses CLI execution arguments (`--dry-run`, `--force-delete`, `--region`). Defaults to dry-run protection.
* `scan_unattached_volumes(ec2_client, dry_run)`: Queries `ec2:DescribeVolumes` for state `available`. Logs or safely removes orphaned storage.
* `scan_unassociated_elastic_ips(ec2_client, dry_run)`: Queries `ec2:DescribeAddresses` to detect allocated IPs lacking active EC2/ENI associations.
* `main()`: Authenticates client, executes evaluation cycles, and outputs structured audit status logs.

---

## Verification & Output Example

Verified output captured from Amazon CloudWatch logs during an automated scan run:

```text
============================================================
 Cloud-Janitor Automation Engine v1.2
 Target Region : eu-central-1
 Mode          : DRY-RUN (Safe)
============================================================

[+] Scanning for unattached EBS volumes (Dry-Run: True)...
    [!] Target found: vol-0428e69323d29c167 (1 GiB, Created: 2026-08-23 20:51:03)
        [DRY-RUN] Would delete volume: vol-0428e69323d29c167

[+] Scanning for unassociated Elastic IPs (Dry-Run: True)...
    ✔ No unused Elastic IPs found.

[✔] Scan cycle complete.
```