---
title: "Nuclei"
type: tool
tags: [scanner, recon, cve]
phase: recon
sources: []
---

## Purpose

Template-based vulnerability scanner.

## Install / setup

```bash
apt install nuclei
```

## Core usage

```bash
# templated scan against a host
nuclei -u https://target.example -severity medium,high,critical
```
