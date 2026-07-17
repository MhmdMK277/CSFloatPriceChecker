# SignPath Foundation Application (2-minute walkthrough)

SignPath Foundation gives qualifying open-source projects free Windows code
signing. Once approved, our releases stop triggering the SmartScreen
"Unknown publisher" warning. The application must be submitted by the
repository owner. Everything below is pre-filled; just copy and paste.

Tracking: [issue #40](https://github.com/MhmdMK277/CSFloatPriceChecker/issues/40)

## Eligibility check (already satisfied)

Their conditions (see [signpath.org/terms](https://signpath.org/terms.html)) vs this repo:

| Requirement | Status |
| --- | --- |
| OSI-approved license, no commercial dual-licensing | Yes: MIT ([LICENSE](LICENSE)) |
| No proprietary components | Yes: all dependencies are OSS |
| Actively maintained | Yes: recent releases and commits |
| Already released in the form to be signed | Yes: `CSFloatTracker-Windows.exe` on [Releases](https://github.com/MhmdMK277/CSFloatPriceChecker/releases) |
| Functionality described on the download page | Yes: README + release notes |
| Signing team owns the source repository | Yes |

## Steps

1. Open **https://signpath.org/apply**
2. Sign in / register with your GitHub account (`MhmdMK277`)
3. Fill the form with:

| Field | Value |
| --- | --- |
| Project name | `CSFloat Tracker` |
| Project URL | `https://github.com/MhmdMK277/CSFloatPriceChecker` |
| Repository URL | `https://github.com/MhmdMK277/CSFloatPriceChecker` |
| License | `MIT` |
| License URL | `https://github.com/MhmdMK277/CSFloatPriceChecker/blob/main/LICENSE` |
| Download / release page | `https://github.com/MhmdMK277/CSFloatPriceChecker/releases` |
| Artifacts to sign | `CSFloatTracker-Windows.exe (PyInstaller onefile executable, built by GitHub Actions from tag pushes)` |
| Build system | `GitHub Actions (.github/workflows/release.yml), builds from tagged commits on the public repository` |
| Project description | `Free, open-source CS2 skin price tracker with deal finder, inventory valuation, and multi-marketplace comparison. Runs locally; distributed as a standalone Windows executable.` |
| Your role | `Owner / maintainer` |

4. Submit. Approval typically takes days to a few weeks.

## After approval

Ping the maintainer bot/agent or follow issue #40: the release workflow gets a
SignPath signing step (`signpath/github-actions-setup@v1`) between the
PyInstaller build and the release publish, and the README gets the SignPath
Foundation attribution they require (a note that binaries are signed by
SignPath Foundation, linked to their site).

## Fallback: Azure Artifact Signing (formerly Trusted Signing)

If SignPath approval stalls, Microsoft's signing service is the paid backup:

- About $10/month (Basic tier)
- Available to organizations in US/CA/EU/UK and individual developers in US/CA
- First-party GitHub Actions integration
- Setup: create an Azure account, complete identity validation, create a
  Trusted Signing account + certificate profile, then add the
  `azure/trusted-signing-action` step to release.yml

Details in issue #40.
