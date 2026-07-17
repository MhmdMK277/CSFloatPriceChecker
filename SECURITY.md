# Security

## Verifying your download

Every release publishes SHA256 checksums (`SHA256SUMS.txt`) alongside the
binaries. To verify on Windows (PowerShell):

```powershell
Get-FileHash .\CSFloatTracker-Windows.exe -Algorithm SHA256
# compare the output against SHA256SUMS.txt from the same release
```

The executables are built from the tagged source by GitHub Actions
([release workflow](.github/workflows/release.yml)); you can audit the exact
build steps and reproduce the build from source.

## Windows SmartScreen warning

The Windows executable is not code-signed yet, so the first launch shows
"Windows protected your PC". Click **More info**, then **Run anyway**. This is
expected for unsigned open-source software and happens once.

Free code signing through SignPath Foundation is in progress; see
[issue #40](https://github.com/MhmdMK277/CSFloatPriceChecker/issues/40) and
[SIGNPATH_APPLICATION.md](SIGNPATH_APPLICATION.md).

## What the app does and does not do

- Runs entirely on your machine; state lives in a local SQLite database
- Your CSFloat API key is stored in the OS keychain (Windows Credential
  Manager, macOS Keychain, Secret Service) and is only ever sent to
  csfloat.com
- Outbound connections go exclusively to csfloat.com (market data),
  api.skinport.com (public price feed), steamcommunity.com (inventory
  import), and Steam's image CDN
- No telemetry, no accounts, no third-party services receive your data

## Reporting a vulnerability

Please open a [GitHub issue](https://github.com/MhmdMK277/CSFloatPriceChecker/issues)
for non-sensitive reports. For anything sensitive (e.g. something that could
expose users' API keys), use GitHub's private vulnerability reporting on this
repository instead of a public issue.
