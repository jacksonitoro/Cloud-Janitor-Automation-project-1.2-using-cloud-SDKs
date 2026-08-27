import argparse
import sys
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient

def parse_args():
    parser = argparse.ArgumentParser(description="Cloud-Janitor: Azure Resource Governance")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Simulate cleanup without deleting (default: True)")
    parser.add_argument("--force-delete", action="store_true", help="Execute live deletion")
    parser.add_argument("--subscription-id", required=True, help="Azure Subscription ID")
    return parser.parse_args()

def scan_unattached_disks(compute_client, dry_run=True):
    print(f"\n[+] Scanning for unattached Azure Managed Disks (Dry-Run: {dry_run})...")
    disks = compute_client.disks.list()
    unattached = [d for d in disks if d.disk_state.lower() == "unattached"]

    if not unattached:
        print("    ✔ No unattached disks found.")
        return

    for disk in unattached:
        print(f"    [!] Target found: {disk.name} (Size: {disk.disk_size_gb} GiB, RG: {disk.id.split('/')[4]})")
        if not dry_run:
            rg_name = disk.id.split('/')[4]
            print(f"        -> Deleting disk {disk.name}...")
            compute_client.disks.begin_delete(rg_name, disk.name).result()
            print(f"        ✔ Disk {disk.name} deleted.")
        else:
            print(f"        [DRY-RUN] Would delete disk: {disk.name}")

def scan_unassociated_public_ips(network_client, dry_run=True):
    print(f"\n[+] Scanning for unassociated Public IPs (Dry-Run: {dry_run})...")
    ips = network_client.public_ip_addresses.list_all()
    unassociated = [ip for ip in ips if ip.ip_configuration is None]

    if not unassociated:
        print("    ✔ No unused Public IPs found.")
        return

    for ip in unassociated:
        print(f"    [!] Target found: {ip.name} (IP: {ip.ip_address}, RG: {ip.id.split('/')[4]})")
        if not dry_run:
            rg_name = ip.id.split('/')[4]
            print(f"        -> Deleting Public IP {ip.name}...")
            network_client.public_ip_addresses.begin_delete(rg_name, ip.name).result()
            print(f"        ✔ Public IP {ip.name} deleted.")
        else:
            print(f"        [DRY-RUN] Would delete Public IP: {ip.name}")

def main():
    args = parse_args()
    is_dry_run = not args.force_delete

    print("=" * 60)
    print(" Cloud-Janitor Automation Engine (Azure Edition v1.2)")
    print(f" Subscription ID : {args.subscription_id}")
    print(f" Mode            : {'DRY-RUN (Safe)' if is_dry_run else 'DELETION (Live)'}")
    print("=" * 60)

    try:
        # DefaultAzureCredential automatically detects Managed Identity in ACI or Azure CLI login locally
        credential = DefaultAzureCredential()
        compute_client = ComputeManagementClient(credential, args.subscription_id)
        network_client = NetworkManagementClient(credential, args.subscription_id)

        scan_unattached_disks(compute_client, dry_run=is_dry_run)
        scan_unassociated_public_ips(network_client, dry_run=is_dry_run)
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {e}")
        sys.exit(1)

    print("\n[✔] Azure scan cycle complete.")

if __name__ == "__main__":
    main()