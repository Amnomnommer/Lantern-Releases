# Release repository boundary

This repository is public. Store only reviewed distribution artifacts, public
certificate material, release metadata and release tooling here. Never copy
the private Lantern repository, personal material, machine audit logs, signing
keys/keystores, access tokens, passwords or recovery bundles into any branch,
commit, workflow output, artifact or release here.

APK signing happens outside this repository. Its workflow verifies pre-signed
bytes against the pinned certificate and never needs a signing secret. Do not
replace the certificate merely to make a candidate pass. Existing Android
installations require the same signing identity for compatible upgrades.

Mobile is a non-authoritative local-processing candidate. Updating the app
requires Android owner confirmation and grants no cognitive-node, memory,
Workstation or general external-action authority. The Workstation channel is
reserved/inactive until separately implemented and accepted.

Run the release contract tests, official APK signature verifier and packaged
manifest checks before publication. Do not overwrite released APK bytes. Treat
publication success and actual phone upgrade acceptance as separate milestones.
