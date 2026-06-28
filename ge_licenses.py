#!/usr/bin/env python3
"""
GE Licenses Manager.

This script automates batch assignment and unassignment of Gemini Enterprise
user licenses using the Google Cloud Discovery Engine API.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error


def get_access_token():
    """Retrieves the OAuth 2.0 access token using gcloud."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error: Failed to retrieve gcloud access token. "
              f"Ensure gcloud is installed and authenticated. Details: {e}",
              file=sys.stderr)
        sys.exit(1)


def make_api_request(url, headers, data=None, method="POST"):
    """Helper function to perform HTTP requests to the Google Cloud APIs."""
    req = urllib.request.Request(
        url,
        headers=headers,
        data=json.dumps(data).encode("utf-8") if data else None,
        method=method
    )
    try:
        with urllib.request.urlopen(req) as response:
            res_data = response.read().decode("utf-8")
            return json.loads(res_data) if res_data else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        print(f"Response: {error_body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Connection Error: {e}", file=sys.stderr)
        sys.exit(1)


def get_project_number(project_id):
    """Retrieves the project number for a given project ID using gcloud."""
    try:
        result = subprocess.run(
            ["gcloud", "projects", "describe", project_id, "--format=value(projectNumber)"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Warning: Failed to retrieve project number for '{project_id}': {e}", file=sys.stderr)
        return ""


def load_emails_from_file(filepath):
    """Reads email addresses from a file. Supports both raw lists and CSV formats (user_licenses.txt)."""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        sys.exit(1)
    
    emails = []
    with open(filepath, "r", encoding="utf-8") as f:
        first_line = True
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            
            # Skip CSV header if present
            if first_line:
                first_line = False
                if line_str.startswith("email") or "license" in line_str:
                    continue
            
            # Handle CSV split
            parts = line_str.split(",")
            email = parts[0].strip()
            
            if email and "@" in email:
                emails.append(email)
    return emails


def format_tier_name(c):
    """Formats the raw subscriptionTier into a human-readable name matching the GCP Console UI."""
    tier = c.get("subscriptionTier") or c.get("subscription_tier") or ""
    config_name = c.get("name", "")
    config_id = config_name.split("/")[-1] if config_name else ""

    # 1. Check for free trial/agentspace
    if "free_trial" in config_id.lower() or c.get("freeTrial") or c.get("free_trial"):
        return "Agentspace Enterprise Plus"

    # 2. Map standard, plus, and all other tiers according to GCP Console specifications
    tier_upper = tier.upper()
    if "SEARCH_AND_ASSISTANT" in tier_upper:
        return "Gemini Enterprise Plus"
    elif "ENTERPRISE" in tier_upper:
        return "Gemini Enterprise Standard"
    elif "SEARCH" in tier_upper:
        return "Gemini Enterprise Standard"
    elif "FRONTLINE_WORKER" in tier_upper:
        return "Gemini Enterprise Frontline"
    elif "FRONTLINE_STARTER" in tier_upper:
        return "Gemini Enterprise Frontline Starter"
    elif "NOTEBOOK_LM" in tier_upper:
        return "Notebook LM Enterprise"
    elif "EDU_PRO" in tier_upper:
        return "Gemini Enterprise Edu Pro"
    elif "EDU" in tier_upper:
        return "Gemini Enterprise Edu"
    elif "AGENTSPACE_STARTER" in tier_upper:
        return "Gemini Business Starter"
    elif "AGENTSPACE_BUSINESS" in tier_upper:
        return "Gemini Business"

    # 3. Fallback: format the tier name
    if tier:
        return tier.replace("SUBSCRIPTION_TIER_", "").replace("_", " ").title()
    return "N/A"


def show_license_analysis_summary(args):
    """Displays a summary analysis of current subscriptions and user license assignments."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": args.project_id
    }

    # 1. Fetch all subscription configs
    url_configs = (
        f"https://{args.endpoint_location}-discoveryengine.googleapis.com/v1/"
        f"projects/{args.project_id}/locations/{args.location}/licenseConfigs"
    )
    try:
        configs_response = make_api_request(url_configs, headers, method="GET")
        configs = configs_response.get("licenseConfigs", [])
    except Exception as e:
        print(f"Warning: Could not fetch subscription configs for summary: {e}", file=sys.stderr)
        configs = []

    # 2. Fetch all user license assignments
    url_licenses = (
        f"https://{args.endpoint_location}-discoveryengine.googleapis.com/v1/"
        f"projects/{args.project_id}/locations/{args.location}/userStores/default_user_store/userLicenses"
    )
    try:
        licenses_response = make_api_request(url_licenses, headers, method="GET")
        user_licenses = licenses_response.get("userLicenses", [])
    except Exception as e:
        print(f"Warning: Could not fetch user license assignments for summary: {e}", file=sys.stderr)
        user_licenses = []

    # 3. Perform analysis
    total_users = len(user_licenses)
    total_subs = len(configs)

    # Map subscription config full resource path to config object
    configs_map = {c.get("name"): c for c in configs}

    # Count assignments per subscription config path
    assignment_counts = {}
    unassigned_count = 0

    for ul in user_licenses:
        config_path = ul.get("licenseConfig") or ul.get("license_config")
        if config_path:
            assignment_counts[config_path] = assignment_counts.get(config_path, 0) + 1
        else:
            unassigned_count += 1

    print("\n" + "=" * 80)
    print(" LICENSE ANALYSIS DASHBOARD")
    print("=" * 80)
    print(f"Total Users in Store:  {total_users}")
    print(f"Total Subscriptions:   {total_subs}")
    print(f"Unassigned Users:      {unassigned_count}")
    print("-" * 80)

    if configs:
        print(f"{'Subscription ID':<40} | {'Tier':<25} | {'State':<10} | {'Limit':<6} | {'Assigned':<8} | {'Available':<9}")
        print("-" * 115)
        for c in configs:
            full_name = c.get("name", "")
            name_parts = full_name.split("/")
            config_id = name_parts[-1] if name_parts else "N/A"

            limit_str = c.get("licenseCount", "0")
            try:
                limit = int(limit_str)
            except ValueError:
                limit = 0

            assigned = assignment_counts.get(full_name, 0)
            available = max(0, limit - assigned)
            state = c.get("state", "N/A")
            
            tier_display = c.get("subscriptionDisplayName") or c.get("subscription_display_name")
            if not tier_display:
                tier_display = format_tier_name(c)

            print(f"{config_id:<40} | {tier_display:<25} | {state:<10} | {limit_str:<6} | {assigned:<8} | {available:<9}")
    else:
        print("No subscription configurations found in this project/location.")

    # Check if there are assigned configurations not found in active configs
    orphaned_configs = []
    for path, count in assignment_counts.items():
        if path not in configs_map:
            sub_id = path.split("/")[-1] if "/" in path else path
            orphaned_configs.append((sub_id, count))

    if orphaned_configs:
        print("-" * 80)
        print("Users assigned to deleted/expired subscriptions:")
        for sub_id, count in orphaned_configs:
            print(f"  - {sub_id}: {count} users")

    print("=" * 105 + "\n")


def list_billing_subscriptions(args):
    """Lists subscription license configurations for a billing account."""
    token = get_access_token()
    billing_acct = args.billing_account_id

    # Billing REST API endpoints are generally global.
    url = f"https://discoveryengine.googleapis.com/v1alpha/billingAccounts/{billing_acct}/billingAccountLicenseConfigs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": args.project_id
    }

    print(f"Fetching subscriptions for billing account '{billing_acct}'...")
    try:
        response = make_api_request(url, headers, method="GET")
        configs = response.get("billingAccountLicenseConfigs", [])
    except Exception as e:
        print(f"Error fetching billing subscriptions: {e}", file=sys.stderr)
        return

    if not configs:
        print(f"No Gemini Enterprise subscriptions found for billing account '{billing_acct}'.")
        return

    print(f"\nBilling Account Subscriptions:")
    print("-" * 120)
    print(f"{'Billing License Config ID':<40} | {'Tier':<25} | {'Limit':<8} | {'State':<10} | {'Term':<20}")
    print("-" * 120)
    for c in configs:
        full_name = c.get("name", "")
        name_parts = full_name.split("/")
        config_id = name_parts[-1] if name_parts else "N/A"

        print(f"{config_id:<40} | {c.get('subscriptionTier', 'N/A'):<25} | {c.get('licenseCount', '0'):<8} | {c.get('state', 'N/A'):<10} | {c.get('subscriptionTerm', 'N/A'):<20}")

        # Print distributions if present
        distributions = c.get("licenseConfigDistributions", {})
        if distributions:
            print("  Distributions:")
            for path, count in distributions.items():
                print(f"    - {path}: {count} seats")
    print("-" * 120)


def distribute_licenses(args):
    """Distributes seats from a billing account subscription config to a project config."""
    token = get_access_token()
    billing_acct = args.billing_account_id
    billing_config_id = args.billing_license_config_id
    target_project = args.target_project_id or args.project_id
    location = args.location
    count = args.license_count

    # Resolve target project ID to target project number
    target_project_num = get_project_number(target_project)
    if not target_project_num:
        print(f"Error: Could not resolve target project number for '{target_project}'.", file=sys.stderr)
        sys.exit(1)

    endpoint = args.endpoint_location
    url = (
        f"https://{endpoint}-discoveryengine.googleapis.com/v1alpha/"
        f"billingAccounts/{billing_acct}/billingAccountLicenseConfigs/{billing_config_id}:distributeLicenseConfig"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": args.project_id
    }

    payload = {
        "projectNumber": target_project_num,
        "location": location,
        "licenseCount": count
    }
    # Optional: licenseConfigId
    if getattr(args, "subscription_id", None):
        payload["licenseConfigId"] = args.subscription_id

    print(f"Distributing {count} licenses to project '{target_project}' ({target_project_num}) in location '{location}'...")
    try:
        make_api_request(url, headers, data=payload, method="POST")
        print("License distribution request completed successfully.")
    except Exception as e:
        print(f"Error distributing licenses: {e}", file=sys.stderr)
        sys.exit(1)


def retract_licenses(args):
    """Retracts (reclaims) seats from a project's local config back to the billing account subscription pool."""
    token = get_access_token()
    billing_acct = args.billing_account_id
    billing_config_id = args.billing_license_config_id
    target_project = args.target_project_id or args.project_id
    location = args.location
    count = args.license_count
    sub_id = args.subscription_id # The project-level licenseConfigId

    if not sub_id:
        print("Error: Project-level Subscription ID (--subscription-id) is required for retraction.", file=sys.stderr)
        sys.exit(1)

    target_project_num = get_project_number(target_project)
    if not target_project_num:
        print(f"Error: Could not resolve target project number for '{target_project}'.", file=sys.stderr)
        sys.exit(1)

    endpoint = args.endpoint_location
    url = (
        f"https://{endpoint}-discoveryengine.googleapis.com/v1alpha/"
        f"billingAccounts/{billing_acct}/billingAccountLicenseConfigs/{billing_config_id}:retractLicenseConfig"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": args.project_id
    }

    # Path: projects/{TARGET_PROJECT_NUMBER}/locations/{LOCATION}/licenseConfigs/{LICENSE_CONFIG_ID}
    license_config_path = f"projects/{target_project_num}/locations/{location}/licenseConfigs/{sub_id}"

    payload = {
        "licenseConfig": license_config_path,
        "licenseCount": count
    }

    print("\n" + "!" * 80)
    print(" WARNING: Retraction is restricted to once per calendar day per project config.")
    print(" Please make sure you are reclaiming the correct number of seats.")
    print("!" * 80 + "\n")

    confirm = input(f"Are you sure you want to retract {count} licenses from config '{sub_id}' in project '{target_project}'? (y/n): ").strip().lower()
    if confirm != "y":
        print("Retraction cancelled.")
        return

    print(f"Retracting {count} licenses from project '{target_project}'...")
    try:
        make_api_request(url, headers, data=payload, method="POST")
        print("License retraction request completed successfully.")
    except Exception as e:
        print(f"Error retracting licenses: {e}", file=sys.stderr)
        sys.exit(1)


def auto_update_licenses_file(args, filepath="user_licenses.txt"):
    """Fetches current user licenses and writes them to a local file."""
    token = get_access_token()
    url = (
        f"https://{args.endpoint_location}-discoveryengine.googleapis.com/v1/"
        f"projects/{args.project_id}/locations/{args.location}/userStores/default_user_store/userLicenses"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": args.project_id
    }

    try:
        response = make_api_request(url, headers, method="GET")
        user_licenses = response.get("userLicenses", [])

        # Create a backup of the existing file to avoid data loss
        if os.path.exists(filepath):
            backup_path = filepath + ".bak"
            try:
                shutil.copy2(filepath, backup_path)
                print(f"Created backup of local file at '{backup_path}'")
            except Exception as e:
                print(f"Warning: Could not create backup file: {e}", file=sys.stderr)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("email,license_config\n")
            for ul in user_licenses:
                email = ul.get("userPrincipal", "")
                config = ul.get("licenseConfig") or ul.get("license_config") or "N/A"
                if email:
                    f.write(f"{email},{config}\n")
        print(f"Automatically updated '{filepath}' with {len(user_licenses)} active records.")
        show_license_analysis_summary(args)
    except Exception as e:
        print(f"Warning: Failed to automatically update '{filepath}': {e}", file=sys.stderr)


def list_subscriptions_with_availability(args):
    """Lists available subscriptions and details license availability limits."""
    token = get_access_token()
    
    # Fetch configs
    url_configs = (
        f"https://{args.endpoint_location}-discoveryengine.googleapis.com/v1/"
        f"projects/{args.project_id}/locations/{args.location}/licenseConfigs"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": args.project_id
    }
    
    print("Fetching active subscriptions and calculating availability...")
    try:
        configs_response = make_api_request(url_configs, headers, method="GET")
        configs = configs_response.get("licenseConfigs", [])
    except Exception as e:
        print(f"Error fetching subscriptions: {e}", file=sys.stderr)
        return

    if not configs:
        print("No subscription configurations found.")
        return

    # Fetch user licenses to calculate counts
    url_licenses = (
        f"https://{args.endpoint_location}-discoveryengine.googleapis.com/v1/"
        f"projects/{args.project_id}/locations/{args.location}/userStores/default_user_store/userLicenses"
    )
    try:
        licenses_response = make_api_request(url_licenses, headers, method="GET")
        user_licenses = licenses_response.get("userLicenses", [])
    except Exception:
        user_licenses = []

    # Count assignments
    assignment_counts = {}
    for ul in user_licenses:
        config_path = ul.get("licenseConfig") or ul.get("license_config")
        if config_path:
            assignment_counts[config_path] = assignment_counts.get(config_path, 0) + 1

    print(f"\nAvailable Subscriptions:")
    print("-" * 140)
    print(f"{'Subscription ID':<40} | {'Tier':<25} | {'State':<10} | {'Limit':<8} | {'Assigned':<10} | {'Available':<10} | {'Term':<15}")
    print("-" * 140)
    for c in configs:
        full_name = c.get("name", "")
        name_parts = full_name.split("/")
        config_id = name_parts[-1] if name_parts else "N/A"

        limit_str = c.get("licenseCount", "0")
        try:
            limit = int(limit_str)
        except ValueError:
            limit = 0

        assigned = assignment_counts.get(full_name, 0)
        available = max(0, limit - assigned)

        tier_display = c.get("subscriptionDisplayName") or c.get("subscription_display_name")
        if not tier_display:
            tier_display = format_tier_name(c)

        print(f"{config_id:<40} | {tier_display:<25} | {c.get('state', 'N/A'):<10} | {limit_str:<8} | {assigned:<10} | {available:<10} | {c.get('subscriptionTerm', 'N/A'):<15}")
    print("-" * 140)


def get_subscription_availability(args, sub_id):
    """Retrieves availability count for a specific subscription ID."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": args.project_id
    }

    # 1. Fetch license config limit
    url_config = (
        f"https://{args.endpoint_location}-discoveryengine.googleapis.com/v1/"
        f"projects/{args.project_id}/locations/{args.location}/licenseConfigs/{sub_id}"
    )
    try:
        config = make_api_request(url_config, headers, method="GET")
        limit_str = config.get("licenseCount", "0")
        limit = int(limit_str)
    except Exception as e:
        print(f"Warning: Failed to fetch license limit for '{sub_id}': {e}", file=sys.stderr)
        return None

    # 2. Fetch user licenses to calculate counts
    url_licenses = (
        f"https://{args.endpoint_location}-discoveryengine.googleapis.com/v1/"
        f"projects/{args.project_id}/locations/{args.location}/userStores/default_user_store/userLicenses"
    )
    try:
        licenses_response = make_api_request(url_licenses, headers, method="GET")
        user_licenses = licenses_response.get("userLicenses", [])
    except Exception:
        user_licenses = []

    if not getattr(args, "project_number", None):
        args.project_number = get_project_number(args.project_id)

    full_name = f"projects/{args.project_number}/locations/{args.location}/licenseConfigs/{sub_id}"
    assigned = sum(1 for ul in user_licenses if (ul.get("licenseConfig") or ul.get("license_config")) == full_name)

    return max(0, limit - assigned)


def assign_licenses(args, emails):
    """Assigns Gemini Enterprise licenses to specified users in batches."""
    token = get_access_token()
    endpoint = args.endpoint_location
    project_id = args.project_id
    location = args.location
    project_num = args.project_number
    sub_id = args.subscription_id

    if not project_num:
        project_num = get_project_number(project_id)
        args.project_number = project_num

    # Validate subscription availability limit before assigning
    available = get_subscription_availability(args, sub_id)
    if available is not None:
        if len(emails) > available:
            print(f"\nWarning: You are trying to assign {len(emails)} licenses, "
                  f"but only {available} slots are available for subscription '{sub_id}'.")
            if available == 0:
                print("Error: No available licenses. Assignment aborted.", file=sys.stderr)
                return
            confirm = input(f"Would you like to assign licenses to the first {available} users and leave the rest unassigned? (y/n): ").strip().lower()
            if confirm != "y":
                print("Assignment cancelled.")
                return
            emails = emails[:available]

    url = (
        f"https://{endpoint}-discoveryengine.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/userStores/default_user_store:batchUpdateUserLicenses"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }

    # License configuration path format
    license_config_path = f"projects/{project_num}/locations/{location}/licenseConfigs/{sub_id}"

    # Batch process to avoid API limits
    batch_size = args.batch_size
    for i in range(0, len(emails), batch_size):
        batch_emails = emails[i:i + batch_size]
        user_licenses = []
        for email in batch_emails:
            user_licenses.append({
                "userPrincipal": email,
                "license_config": license_config_path
            })

        payload = {
            "inlineSource": {
                "userLicenses": user_licenses,
                "updateMask": {
                    "paths": ["userPrincipal", "license_config"]
                }
            },
            "deleteUnassignedUserLicenses": False
        }

        print(f"Assigning licenses to batch of {len(batch_emails)} users...")
        make_api_request(url, headers, data=payload)
        print("Batch assignment completed successfully.")


def unassign_licenses(args, emails):
    """Unassigns Gemini Enterprise licenses from specified users in batches (retains users)."""
    token = get_access_token()
    endpoint = args.endpoint_location
    project_id = args.project_id
    location = args.location

    url = (
        f"https://{endpoint}-discoveryengine.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/userStores/default_user_store:batchUpdateUserLicenses"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }

    batch_size = args.batch_size
    for i in range(0, len(emails), batch_size):
        batch_emails = emails[i:i + batch_size]
        user_licenses = []
        for email in batch_emails:
            user_licenses.append({
                "userPrincipal": email,
                "license_config": ""
            })

        payload = {
            "inlineSource": {
                "userLicenses": user_licenses,
                "updateMask": {
                    "paths": ["userPrincipal", "license_config"]
                }
            },
            "deleteUnassignedUserLicenses": False
        }

        print(f"Unassigning licenses from batch of {len(batch_emails)} users...")
        make_api_request(url, headers, data=payload)
        print("Batch unassignment completed successfully.")


def migrate_licenses(args):
    """Migrates users from an old subscription config to a new subscription config."""
    if not args.old_subscription_id or not args.new_subscription_id:
        print("Error: Both --old-subscription-id and --new-subscription-id are required for migration.", file=sys.stderr)
        sys.exit(1)

    token = get_access_token()
    endpoint = args.endpoint_location
    project_id = args.project_id
    location = args.location

    # 1. Try to fetch current active assignments from GCP API
    url = (
        f"https://{endpoint}-discoveryengine.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/userStores/default_user_store/userLicenses"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }

    print("Fetching active user licenses from GCP to identify users to migrate...")
    emails_to_migrate = []

    try:
        response = make_api_request(url, headers, method="GET")
        user_licenses = response.get("userLicenses", [])
        for ul in user_licenses:
            email = ul.get("userPrincipal", "")
            config = ul.get("licenseConfig") or ul.get("license_config") or ""
            if email and args.old_subscription_id in config:
                emails_to_migrate.append(email)
    except Exception as e:
        print(f"Warning: Failed to fetch live licenses from GCP API: {e}", file=sys.stderr)

    # 2. Fall back to local file if no users were found via API
    if not emails_to_migrate:
        emails_file = args.emails_file or "user_licenses.txt"
        if os.path.exists(emails_file):
            print(f"No active assignments for '{args.old_subscription_id}' found via API. "
                  f"Checking local database '{emails_file}'...")
            with open(emails_file, "r", encoding="utf-8") as f:
                first_line = True
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    if first_line:
                        first_line = False
                        if line_str.startswith("email") or "license" in line_str:
                            continue
                    parts = line_str.split(",")
                    email = parts[0].strip()
                    config = parts[1].strip() if len(parts) > 1 else ""

                    if args.old_subscription_id in config:
                        emails_to_migrate.append(email)
        else:
            print(f"No active assignments for '{args.old_subscription_id}' found via API, "
                  f"and local file '{emails_file}' does not exist.")
            return

    if not emails_to_migrate:
        print(f"No users found to migrate from '{args.old_subscription_id}'.")
        return

    print(f"Found {len(emails_to_migrate)} users to migrate from '{args.old_subscription_id}' to '{args.new_subscription_id}'.")
    confirm = input(f"Proceed with migration of {len(emails_to_migrate)} users? (y/n): ").strip().lower()
    if confirm != "y":
        print("Migration cancelled.")
        return

    # Set the subscription_id to new_subscription_id for the assign_licenses function
    args.subscription_id = args.new_subscription_id
    if not args.project_number:
        auto_num = get_project_number(args.project_id)
        if auto_num:
            args.project_number = auto_num
        else:
            print("Error: Project Number is required for migration and could not be auto-discovered.", file=sys.stderr)
            sys.exit(1)

    assign_licenses(args, emails_to_migrate)
    # Auto-update the user_licenses.txt file from the API after assignment
    auto_update_licenses_file(args, filepath=args.emails_file or "user_licenses.txt")


def list_licenses(args):
    """Lists currently assigned user licenses."""
    token = get_access_token()
    endpoint = args.endpoint_location
    project_id = args.project_id
    location = args.location

    url = (
        f"https://{endpoint}-discoveryengine.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/userStores/default_user_store/userLicenses"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }

    print("Fetching active user licenses...")
    response = make_api_request(url, headers, method="GET")
    
    user_licenses = response.get("userLicenses", [])
    if not user_licenses:
        print("No active user licenses found.")
        return

    print(f"\nFound {len(user_licenses)} active user licenses:")
    print("-" * 80)
    print(f"{'User Principal':<40} | {'License Config / Subscription ID'}")
    print("-" * 80)
    for ul in user_licenses:
        print(f"{ul.get('userPrincipal', 'N/A'):<40} | {ul.get('licenseConfig') or ul.get('license_config', 'N/A')}")
    print("-" * 80)


def interactive_menu():
    """Displays interactive CLI menu loop for GE License management."""
    print("=" * 80)
    print("GE Licenses Manager - Interactive Mode")
    print("=" * 80)

    while True:
        project_id = input("Enter GCP Project ID (or type 'exit' to quit): ").strip()
        if not project_id:
            print("Error: GCP Project ID is required.", file=sys.stderr)
            continue
        if project_id.lower() == "exit":
            return

        project_num = get_project_number(project_id)
        if not project_num:
            print(f"Error: Project ID '{project_id}' is invalid, does not exist, or you do not have access.", file=sys.stderr)
            print("Please try again.\n")
            continue
        break

    location = input("Enter Location (e.g. global, us, eu): ").strip().lower()
    if not location:
        print("Error: Location is required.", file=sys.stderr)
        return

    # Setup default arguments
    class Args:
        pass
    
    args = Args()
    args.project_id = project_id
    args.location = location
    args.endpoint_location = location
    args.batch_size = 100
    args.project_number = project_num

    # Step 1: Prompt before auto-updating user_licenses.txt
    sync_choice = input("Do you want to sync 'user_licenses.txt' with live GCP data first? (y/n) [default: y]: ").strip().lower()
    if sync_choice != "n":
        auto_update_licenses_file(args, filepath="user_licenses.txt")
    else:
        print("Using local 'user_licenses.txt' file mapping.")

    while True:
        print("\nSelect an action:")
        print("1. Batch Assign Licenses")
        print("2. Batch Unassign Licenses")
        print("3. Migrate Subscriptions (Contract Changed)")
        print("4. Manage Project Allocations (Distribute/Retract)")
        print("5. Exit")

        choice = input("Enter choice (1-5): ").strip()

        if choice == "1":
            print("\n--- Batch Assign Licenses ---")
            list_subscriptions_with_availability(args)

            if project_num:
                print(f"Project Number (auto-discovered): {project_num}")
                selected_project_num = project_num
            else:
                selected_project_num = input("Enter GCP Project Number: ").strip()
                if not selected_project_num:
                    print("Error: Project Number is required.")
                    continue
                if not selected_project_num.isdigit():
                    print("Error: Project Number must be numeric.")
                    continue

            sub_id = input("Enter Subscription ID to assign: ").strip()
            if not sub_id:
                print("Error: Subscription ID is required.")
                continue

            args.project_number = selected_project_num
            args.subscription_id = sub_id

            email_mode = input("Select email input: (1) Typed list, (2) Load from file: ").strip()
            emails = []
            if email_mode == "1":
                emails_input = input("Enter comma-separated email list: ").strip()
                emails = [e.strip() for e in emails_input.split(",") if e.strip()]
            elif email_mode == "2":
                file_path = input("Enter path to emails file [default: user_licenses.txt]: ").strip() or "user_licenses.txt"
                emails = load_emails_from_file(file_path)

            if not emails:
                print("Error: No emails provided.")
                continue

            assign_licenses(args, emails)
            # Update licenses.txt automatically after changes
            auto_update_licenses_file(args)

        elif choice == "2":
            print("\n--- Batch Unassign Licenses ---")
            email_mode = input("Select email input: (1) Typed list, (2) Load from file: ").strip()
            emails = []
            if email_mode == "1":
                emails_input = input("Enter comma-separated email list: ").strip()
                emails = [e.strip() for e in emails_input.split(",") if e.strip()]
            elif email_mode == "2":
                file_path = input("Enter path to emails file [default: user_licenses.txt]: ").strip() or "user_licenses.txt"
                emails = load_emails_from_file(file_path)

            if not emails:
                print("Error: No emails provided.")
                continue

            confirm = input(f"Are you sure you want to unassign licenses from {len(emails)} users? (y/n): ").strip().lower()
            if confirm == "y":
                unassign_licenses(args, emails)
                # Update licenses.txt automatically after changes
                auto_update_licenses_file(args)
            else:
                print("Unassignment cancelled.")

        elif choice == "3":
            print("\n--- Migrate Subscriptions (Contract Changed) ---")
            print("This option updates user assignments from an old Subscription ID to a new one using local database mappings.")

            old_sub = input("Enter Old Subscription ID (to migrate users from): ").strip()
            if not old_sub:
                print("Error: Old Subscription ID is required.")
                continue

            new_sub = input("Enter New Subscription ID (to migrate users to): ").strip()
            if not new_sub:
                print("Error: New Subscription ID is required.")
                continue

            file_path = input("Enter path to emails file containing mappings [default: user_licenses.txt]: ").strip() or "user_licenses.txt"

            if project_num:
                args.project_number = project_num
            else:
                selected_project_num = input("Enter GCP Project Number: ").strip()
                if not selected_project_num or not selected_project_num.isdigit():
                    print("Error: Valid GCP Project Number is required.")
                    continue
                args.project_number = selected_project_num

            args.old_subscription_id = old_sub
            args.new_subscription_id = new_sub
            args.emails_file = file_path

            migrate_licenses(args)

        elif choice == "4":
            while True:
                print("\n--- Manage Project Allocations ---")
                print("1. List Billing Account Subscriptions & Distributions")
                print("2. Distribute Licenses to a Project")
                print("3. Retract Licenses from a Project")
                print("4. Return to Main Menu")

                alloc_choice = input("Enter choice (1-4): ").strip()
                if alloc_choice == "1":
                    billing_acct = input("Enter Google Cloud Billing Account ID (e.g. 012345-6789AB-CDEF01): ").strip()
                    if not billing_acct:
                        print("Error: Billing Account ID is required.")
                        continue
                    args.billing_account_id = billing_acct
                    list_billing_subscriptions(args)
                elif alloc_choice == "2":
                    billing_acct = input("Enter Google Cloud Billing Account ID: ").strip()
                    if not billing_acct:
                        print("Error: Billing Account ID is required.")
                        continue
                    billing_config = input("Enter Billing License Config ID: ").strip()
                    if not billing_config:
                        print("Error: Billing License Config ID is required.")
                        continue

                    target_proj = input(f"Enter Target Project ID [default: {project_id}]: ").strip() or project_id
                    license_count_str = input("Enter number of licenses to distribute: ").strip()
                    if not license_count_str.isdigit():
                        print("Error: License count must be a numeric value.")
                        continue

                    # Optional license config ID
                    opt_sub_id = input("Enter existing project License Config ID (optional, hit Enter to create new): ").strip()

                    args.billing_account_id = billing_acct
                    args.billing_license_config_id = billing_config
                    args.target_project_id = target_proj
                    args.license_count = int(license_count_str)
                    args.subscription_id = opt_sub_id if opt_sub_id else None

                    distribute_licenses(args)
                elif alloc_choice == "3":
                    billing_acct = input("Enter Google Cloud Billing Account ID: ").strip()
                    if not billing_acct:
                        print("Error: Billing Account ID is required.")
                        continue
                    billing_config = input("Enter Billing License Config ID: ").strip()
                    if not billing_config:
                        print("Error: Billing License Config ID is required.")
                        continue

                    target_proj = input(f"Enter Target Project ID [default: {project_id}]: ").strip() or project_id
                    opt_sub_id = input("Enter project License Config ID (required): ").strip()
                    if not opt_sub_id:
                        print("Error: Project License Config ID is required.")
                        continue

                    license_count_str = input("Enter number of licenses to retract: ").strip()
                    if not license_count_str.isdigit():
                        print("Error: License count must be a numeric value.")
                        continue

                    args.billing_account_id = billing_acct
                    args.billing_license_config_id = billing_config
                    args.target_project_id = target_proj
                    args.subscription_id = opt_sub_id
                    args.license_count = int(license_count_str)

                    retract_licenses(args)
                elif alloc_choice == "4":
                    break
                else:
                    print("Invalid choice. Please select 1, 2, 3, or 4.")

        elif choice == "5":
            print("\nExiting. Goodbye!")
            break
        else:
            print("Invalid choice. Please select 1, 2, 3, 4, or 5.")


def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    parser = argparse.ArgumentParser(
        description="Batch manage Gemini Enterprise user licenses."
    )

    parser.add_argument(
        "--action",
        choices=["assign", "unassign", "migrate", "list", "list-subscriptions", "distribute", "retract", "list-billing-subscriptions"],
        required=True,
        help="Action to perform: assign, unassign, migrate, list, list-subscriptions, distribute, retract, or list-billing-subscriptions."
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="GCP Project ID."
    )
    parser.add_argument(
        "--project-number",
        help="GCP Project Number (required for assignment/migration)."
    )
    parser.add_argument(
        "--subscription-id",
        help="Subscription ID / License Config ID (required for assignment/retraction)."
    )
    parser.add_argument(
        "--old-subscription-id",
        help="Old Subscription ID / License Config ID (required for migration)."
    )
    parser.add_argument(
        "--new-subscription-id",
        help="New Subscription ID / License Config ID (required for migration)."
    )
    parser.add_argument(
        "--billing-account-id",
        help="GCP Billing Account ID (required for distribution/retraction/billing-list)."
    )
    parser.add_argument(
        "--billing-license-config-id",
        help="Billing License Config ID / Subscription ID (required for distribution/retraction)."
    )
    parser.add_argument(
        "--target-project-id",
        help="Target GCP Project ID for license distribution/retraction (optional, defaults to --project-id)."
    )
    parser.add_argument(
        "--license-count",
        type=int,
        help="Number of licenses to distribute or retract (required for distribution/retraction)."
    )
    parser.add_argument(
        "--location",
        default="global",
        help="Data store location (default: global)."
    )
    parser.add_argument(
        "--endpoint-location",
        default="global",
        help="API regional endpoint: global, us, or eu (default: global)."
    )
    parser.add_argument(
        "--emails",
        help="Comma-separated list of user emails."
    )
    parser.add_argument(
        "--emails-file",
        help="Path to a text file with one email address per line or CSV file (default: user_licenses.txt)."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of users to process in each API request batch (default: 100)."
    )

    args = parser.parse_args()

    # Parameter validation
    if args.action in ["assign", "unassign"]:
        emails = []
        if args.emails:
            emails.extend([e.strip() for e in args.emails.split(",") if e.strip()])
        if args.emails_file:
            emails.extend(load_emails_from_file(args.emails_file))

        if not emails:
            parser.error("You must specify either --emails or --emails-file.")

        # De-duplicate emails
        emails = list(set(emails))

        if args.action == "assign":
            if not args.project_number:
                auto_num = get_project_number(args.project_id)
                if auto_num:
                    args.project_number = auto_num
                else:
                    parser.error("--project-number is required for assigning licenses and could not be auto-discovered.")
            if not args.subscription_id:
                parser.error("--subscription-id is required for assigning licenses.")

            assign_licenses(args, emails)
        elif args.action == "unassign":
            unassign_licenses(args, emails)

    elif args.action == "migrate":
        migrate_licenses(args)
    elif args.action == "list":
        list_licenses(args)
    elif args.action == "list-subscriptions":
        list_subscriptions_with_availability(args)
    elif args.action == "list-billing-subscriptions":
        if not args.billing_account_id:
            parser.error("--billing-account-id is required for listing billing account subscriptions.")
        list_billing_subscriptions(args)
    elif args.action == "distribute":
        if not args.billing_account_id:
            parser.error("--billing-account-id is required for distributing licenses.")
        if not args.billing_license_config_id:
            parser.error("--billing-license-config-id is required for distributing licenses.")
        if args.license_count is None or args.license_count <= 0:
            parser.error("--license-count must be a positive integer for distributing licenses.")
        distribute_licenses(args)
    elif args.action == "retract":
        if not args.billing_account_id:
            parser.error("--billing-account-id is required for retracting licenses.")
        if not args.billing_license_config_id:
            parser.error("--billing-license-config-id is required for retracting licenses.")
        if not args.subscription_id:
            parser.error("--subscription-id (project-level subscription ID) is required for retracting licenses.")
        if args.license_count is None or args.license_count <= 0:
            parser.error("--license-count must be a positive integer for retracting licenses.")
        retract_licenses(args)


if __name__ == "__main__":
    main()
