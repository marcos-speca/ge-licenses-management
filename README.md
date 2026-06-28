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
   git clone <REPOSITORY_URL>
   cd ge_licenses_management
   ```
3. Run the script directly (it is already authenticated):
   ```bash
   python3 ge_licenses.py --project-id YOUR_PROJECT_ID --interactive
   ```

---

## Authentication

The script does not require exporting local Service Account JSON keys. It utilizes the active authenticated session from your local CLI (`gcloud`) by executing `gcloud auth print-access-token` automatically in the background to retrieve OAuth 2.0 access tokens.

To authenticate your terminal before running the script:
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
To start the guided terminal menu for step-by-step operations:
```bash
python3 ge_licenses.py --project-id YOUR_PROJECT_ID --interactive
```

### 2. Direct CLI Commands

#### List Subscriptions (Contracts) and Assignments
Lists all subscriptions in the project (IDs, tiers, limits, assigned/available seats, and expiration dates) along with user assignments:
```bash
python3 ge_licenses.py --project-id YOUR_PROJECT_ID list
```

#### Sync Local Mappings File (`user_licenses.txt`)
Fetches all active license assignments from the GCP project and saves them locally to `user_licenses.txt` to act as a backup or input file:
```bash
python3 ge_licenses.py --project-id YOUR_PROJECT_ID sync
```

#### Batch Assign/Distribute Licenses
Assigns a specific subscription license config to all email addresses listed in a local text file:
```bash
python3 ge_licenses.py --project-id YOUR_PROJECT_ID distribute --subscription-id SUBSCRIPTION_ID --emails-file user_licenses.txt
```

#### Batch Remove/Retract Licenses
Removes licenses for all email addresses listed in the local text file (without deleting the users from the store):
```bash
python3 ge_licenses.py --project-id YOUR_PROJECT_ID retract --emails-file user_licenses.txt
```

---

## Input / Backup File Format (`user_licenses.txt`)

The input file accepts one email address per line or the CSV format exported by the script:
```text
user1@company.com
user2@company.com
```

---

## Git Ignored Files (.gitignore)
To prevent committing sensitive credential files or PII (user emails), the following files are ignored in the `.gitignore`:
*   `service_account_key.json`
*   `user_licenses.txt`
*   `user_licenses.txt.bak`
*   `__pycache__/`
