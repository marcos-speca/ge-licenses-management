# GE Licenses Manager (ge_licenses.py)

A Python utility script designed to manage **Gemini Enterprise** (Standard and Plus) licenses at the project level in Google Cloud Platform (GCP).

The script interacts directly with the Vertex AI Discovery Engine API (`discoveryengine.googleapis.com`) to list subscriptions, distribute user licenses, remove/retract licenses, and sync assignments in batch.

---

## Prerequisites

1. **Python 3.6+**
2. **Google Cloud CLI (`gcloud`)** installed and authenticated.
3. Required GCP permissions (e.g. `Discovery Engine Admin` or equivalent permissions to manage user licenses).

---

## Running in Google Cloud Shell (Recommended)

Google Cloud Shell has the Google Cloud SDK (`gcloud`), Python 3, and Git pre-installed, and it is automatically authenticated with your active GCP console session.

1. Open **Google Cloud Shell** from the GCP Console.
2. Clone this repository:
   ```bash
   git clone https://github.com/marcos-speca/ge-licenses-management.git
   cd ge-licenses-management
   ```
3. Run the script directly (it is already authenticated):
   ```bash
   python3 ge_licenses.py
   ```

---

## Authentication

The script does not require exporting local Service Account JSON keys. It utilizes the active authenticated session from your local CLI (`gcloud`) by executing `gcloud auth print-access-token` automatically in the background to retrieve OAuth 2.0 access tokens.

> [!NOTE]
> If you are running the script inside **Google Cloud Shell**, you do not need to execute `gcloud auth login`. Google Cloud Shell is automatically authenticated with your active GCP console session.

To authenticate your local terminal before running the script:
```bash
gcloud auth login
```
Or, if you want to use a Service Account:
```bash
gcloud auth activate-service-account --key-file=YOUR_KEY.json
```

---

## Execution Modes

The utility can be run in interactive mode (guided console menu) or using direct CLI command line arguments.

### 1. Interactive Mode (Recommended)
To start the guided terminal menu for step-by-step operations, run without arguments:
```bash
python3 ge_licenses.py
```
> [!WARNING]
> Upon startup, the interactive mode will warn you that a local temporary cache file `user_licenses.txt` will be created during the session and deleted upon exit. You will be prompted to confirm if you want to proceed.

If you choose to proceed, the script will automatically synchronize the active license assignments from GCP to the local temporary cache file. When exiting the interactive mode (or if the script is interrupted), this temporary file and its backup will be deleted to keep your workspace clean.

If you load users from `user_licenses.txt` for a batch assignment and some users already have active licenses, the script will automatically ask whether you want to assign only to unassigned/expired users or to everyone.

### 2. Direct CLI Commands

#### List User License Assignments
Lists all users in the store and their currently assigned subscriptions:
```bash
python3 ge_licenses.py --action list --project-id YOUR_PROJECT_ID
```

#### List Subscriptions (Contracts) and Availability
Lists all active/expired subscription configurations, limits, assigned seats, and available seats:
```bash
python3 ge_licenses.py --action list-subscriptions --project-id YOUR_PROJECT_ID
```

#### Batch Assign Licenses
Assigns a specific subscription license config to all email addresses listed in a local text file:
```bash
python3 ge_licenses.py --action assign --project-id YOUR_PROJECT_ID --subscription-id SUBSCRIPTION_ID --emails-file user_licenses.txt
```
To only assign licenses to users who **do not** already have an active license assigned, add the `--only-unassigned` flag:
```bash
python3 ge_licenses.py --action assign --project-id YOUR_PROJECT_ID --subscription-id SUBSCRIPTION_ID --emails-file user_licenses.txt --only-unassigned
```

#### Batch Unassign Licenses
Removes licenses for all email addresses listed in the local text file (without deleting the users from the store):
```bash
python3 ge_licenses.py --action unassign --project-id YOUR_PROJECT_ID --emails-file user_licenses.txt
```

#### Migrate Subscriptions (Contract Changed)
Migrates users from an old subscription ID to a new one:
```bash
python3 ge_licenses.py --action migrate --project-id YOUR_PROJECT_ID --old-subscription-id OLD_SUB_ID --new-subscription-id NEW_SUB_ID --emails-file user_licenses.txt
```

---

## Input / Backup File Format (`user_licenses.txt`)

The input file accepts one email address per line or the CSV format exported by the script:
```text
email,license_config
user1@company.com,projects/267339081837/locations/global/licenseConfigs/internal_gemini_ent_plus
user2@company.com,N/A
```

---
