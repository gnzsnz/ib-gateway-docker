# Security policy

## Reporting a vulnerability

Use [Report a vulnerability](https://github.com/gnzsnz/ib-gateway-docker/security/advisories/new)
to report a suspected vulnerability in this repository's Docker build, scripts,
or configuration privately. Include the image tag and digest, platform, affected
component and version, and a description of the expected impact. Remove account
details, credentials, and tokens from logs or attachments.

For a vulnerability in IB Gateway or a library bundled by Interactive Brokers,
report the underlying issue to Interactive Brokers through its support channels.
If the Docker packaging affects exposure or needs a change, include that detail
in the report to this project.

## Image scanning

The [image scan workflow](.github/workflows/image-security-scan.yml) scans the
published IB Gateway stable and latest images weekly and on demand for Linux
amd64 and arm64. Each scan publishes a JSON report with all severities and a
SARIF artifact for HIGH and CRITICAL findings. To send SARIF to GitHub code
scanning, enable code scanning for the repository and set the repository Actions
variable `TRIVY_UPLOAD_SARIF` to `true`. Uploads run on the default branch.

Findings are informational. The workflow runs independently of image publishing.
See the [IB Gateway JAR findings](docs/ib-gateway-jar-findings.md) for the scan
baseline and reproduction steps.
