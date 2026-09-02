---
title: "Writeup Reproduction"
type: technique
tags: [methodology, testing, ctf, evidence, false-positives]
phase: recon
date_created: 2026-09-02
date_updated: 2026-09-02
sources: []
---

## What it is

How to use a published writeup / chain on a target without destroying its diagnostic value. The
failure this page prevents: a published chain is adapted (payload rewritten, delivery channel
changed, framing altered) before it ever fires once in its exact form, it does not land, and the
failure is attributed to the TARGET ("patched", "wrong version") instead of the adaptation. That
false verdict then closes the vector for every later session.

## Rule 1: exact-first

Run the published chain's EXACT form before any adaptation: same payload, same framing, same
delivery channel (chat UI vs raw API POST, browser vs curl, the tool the author used). An
adaptation is a one-variable experiment that needs a known-good baseline; adapt before the baseline
exists and every failure is unattributable: was it the payload, the delivery channel, or the target
version? Retarget only the values that MUST change on your setup (the exfil host / callback
domain), keep everything else byte-identical.

## Rule 2: one variable at a time

Only after the exact form is proven working (or proven dead on a channel you PROVED observable) do
you adapt, and then one variable per run: the sink variant, or the delivery channel, or the
framing. A failure then names its cause. Three simultaneous deviations with a negative result
prove nothing about any of the three.

## Rule 3: transcribe every artifact, not just prose

A writeup's screenshots carry ground truth the prose does not state: source IPs, User-Agent,
Origin/Referer headers, log-line formats, UI schema, old-version behavior. Authors redact the
answer values; the surroundings still yield the decisive intel (WHERE execution happened, in WHICH
context, against WHICH version). Vision-transcribe every image at first contact, not days after
the text was "fully read". A listener-log screenshot can prove the exploit ran from the target host
in a headless-browser context the prose never mentions.

## Rule 4: version drift

Rooms and products bump versions silently; the same URL can behave differently on a new instance
without the technique being "patched". Re-test the published chain verbatim on EACH new instance
before concluding anything, and before trusting the negative, prove the observation channel (a
file-logged listener you have actually read, or a self-test hit on the same path): see
[[Safe Probing and Controls]]. An unobservable channel plus an adapted payload is how "I got the
test wrong" becomes "the box was patched".

Related: [[LLM Attacks]] (watcher-bot render as the gate-bypass execution context, found by
transcribing a writeup screenshot).

<!-- promoted-slug: writeup-reproduction -->
