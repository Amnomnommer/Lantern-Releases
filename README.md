# Lantern Releases

Public distribution for Lantern's mobile APK and future Workstation packages.
Lantern's cognitive core, personal state and signing keys are not stored here.

## Android candidate channel

The mobile app checks this repository's public GitHub Releases when opened.
It offers a newer eligible `mobile-debug-vN` release without a GitHub login.
Download-and-verify checks the exact asset hash and size, installed application
identity, strictly newer version and matching signing certificate. Android then
asks the owner to confirm installation; silent installation is not enabled.

The first persistent-signing baseline is being prepared. No current release is
claimed until the verified publication workflow completes. Old independently
signed debug test APKs may need one uninstall before installing that baseline.
Afterwards, compatible updates retain the same Android application identity.

This remains a candidate local-processing app. Workstation connection,
authoritative memory, enrollment, posting and general external action authority
are not enabled. Updates do not turn this phone into an authoritative Lantern.

## Release process

1. Build and test the mobile client in the development repository.
2. Sign the reviewed APK outside this public repository with the persistent key.
3. Commit only that pre-signed APK and its bounded metadata under
   `incoming/mobile-debug-vN/`.
4. The read-only validation job checks metadata, Android's official APK signature
   verification, certificate pin, version, package and manifest permissions.
5. A separate job uploads the verified bytes, checks GitHub's returned hashes,
   and publishes the release. Existing release bytes are never overwritten.

Only the public certificate fingerprint belongs in `channels/`. **Never upload a
private signing key, keystore, recovery file, password, access token, private
database, personal project, or development machine audit files here.**

Public release policy tests run on every infrastructure change. Actual phone
upgrade acceptance is recorded separately from CI validation.

## Workstation channel

`workstation-vN` is reserved and inactive. There is no Workstation updater or
automatic installation service in this repository. Any later package must pass
its own validation and owner-controlled activation/rollback process.
