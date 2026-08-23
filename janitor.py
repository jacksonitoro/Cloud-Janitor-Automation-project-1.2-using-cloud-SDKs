import argparse
import sys
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def parse_args():
    parser = argparse.ArgumentParser(description="Cloud-Janitor: Automated Cloud Resource Governance")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate cleanup actions without deleting resources (default: True)"
    )
    parser.add_argument(
        "--force-delete",
        action="store_true",
        help="Execute actual resource deletion (overrides --dry-run)"
    )
    parser.add_argument(
        "--region",
        default="eu-central-1",
        help="Target AWS region (default: eu-central-1)"
    )
    return parser.parse_args()

def scan_unattached_volumes(ec2_client, dry_run=True):
    print(f"\n[+] Scanning for unattached EBS volumes (Dry-Run: {dry_run})...")
    try:
        response = ec2_client.describe_volumes(
            Filters=[{'Name': 'status', 'Values': ['available']}]
        )
        volumes = response.get('Volumes', [])
        
        if not volumes:
            print("    ✔ No unattached volumes found.")
            return

        for vol in volumes:
            vol_id = vol['VolumeId']
            size_gb = vol['Size']
            created_at = vol['CreateTime'].strftime("%Y-%m-%d %H:%M:%S")
            print(f"    [!] Target found: {vol_id} ({size_gb} GiB, Created: {created_at})")

            if not dry_run:
                print(f"        -> Deleting volume {vol_id}...")
                ec2_client.delete_volume(VolumeId=vol_id)
                print(f"        ✔ Volume {vol_id} deleted.")
            else:
                print(f"        [DRY-RUN] Would delete volume: {vol_id}")

    except ClientError as e:
        print(f"    [ERROR] AWS API error: {e}")
    except Exception as e:
        print(f"    [ERROR] Unexpected error: {e}")

def scan_unassociated_elastic_ips(ec2_client, dry_run=True):
    print(f"\n[+] Scanning for unassociated Elastic IPs (Dry-Run: {dry_run})...")
    try:
        response = ec2_client.describe_addresses()
        eips = response.get('Addresses', [])
        
        unassociated = [eip for eip in eips if 'AssociationId' not in eip and 'InstanceId' not in eip]
        if not unassociated:
            print("    ✔ No unused Elastic IPs found.")
            return

        for eip in unassociated:
            alloc_id = eip.get('AllocationId')
            ip = eip.get('PublicIp')
            print(f"    [!] Target found: Elastic IP {ip} (AllocationId: {alloc_id})")

            if not dry_run:
                print(f"        -> Releasing Elastic IP {ip}...")
                ec2_client.release_address(AllocationId=alloc_id)
                print(f"        ✔ Elastic IP {ip} released.")
            else:
                print(f"        [DRY-RUN] Would release Elastic IP: {ip}")

    except ClientError as e:
        print(f"    [ERROR] AWS API error: {e}")

def main():
    args = parse_args()
    is_dry_run = not args.force_delete

    print("=" * 60)
    print(" Cloud-Janitor Automation Engine v1.2")
    print(f" Target Region : {args.region}")
    print(f" Mode          : {'DRY-RUN (Safe)' if is_dry_run else 'DELETION (Live)'}")
    print("=" * 60)

    try:
        ec2 = boto3.client('ec2', region_name=args.region)
        scan_unattached_volumes(ec2, dry_run=is_dry_run)
        scan_unassociated_elastic_ips(ec2, dry_run=is_dry_run)
    except NoCredentialsError:
        print("\n[CRITICAL] No AWS credentials found. Pass credentials via environment or ~/.aws mount.")
        sys.exit(1)

    print("\n[✔] Scan cycle complete.")

if __name__ == "__main__":
    main()