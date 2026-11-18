# IB Gateway JAR findings

On 2026-11-18, Trivy 0.76.2 scanned the following published
`ghcr.io/gnzsnz/ib-gateway` images for `linux/amd64`. The vulnerability
database was updated at 07:15 UTC and the Java index at 00:58 UTC that day.

| Channel | Gateway version | Linux amd64 manifest digest |
| --- | --- | --- |
| `stable` | `10.50.1h` | `sha256:2c293d45d78315d03f431fa96c715266481bf5acd6ed94a0cf90f332989e11ae` |
| `latest` | `10.52.1d` | `sha256:c529b6e9d13bf6bd95517cb457047de876e6d13943c0bfb91980395097294db1` |

Trivy reported **12 HIGH, 13 MEDIUM and 0 CRITICAL** JAR findings in each
image, with identical package versions and CVE IDs in both. All 12 HIGH
findings came from JARs under `/home/ibgateway/Jts/ibgateway/<version>/jars/`.
The six HIGH findings reported in [issue #370](https://github.com/gnzsnz/ib-gateway-docker/issues/370)
were still present, alongside six additional HIGH Jackson findings in this
snapshot.

| Bundled JAR | Version | HIGH findings from #370 | Additional HIGH findings in this scan |
| --- | --- | --- | --- |
| `jackson-core` | `2.12.3` | CVE-2025-52999 | CVE-2026-68494, CVE-2026-89425 |
| `jackson-databind` | `2.12.3` | CVE-2020-36518, CVE-2021-46877, CVE-2022-42003, CVE-2022-42004 | CVE-2026-54512, CVE-2026-54513, CVE-2026-91776, CVE-2026-91777 |
| `commons-io` | `2.11.0` | CVE-2024-47554 | — |

These findings match installed components to advisories. Whether an affected
code path is reachable in IB Gateway requires separate analysis. Counts can
change as advisories are added or updated.

## Reproduce the scan

Run from a directory without a Trivy configuration or ignore file. Substitute
the other manifest digest from the table to scan its image.

```sh
trivy image --image-src remote --platform linux/amd64 --scanners vuln \
  --timeout 15m --format json --output trivy.json \
  ghcr.io/gnzsnz/ib-gateway@sha256:c529b6e9d13bf6bd95517cb457047de876e6d13943c0bfb91980395097294db1
jq '.Results[] | select(.Type == "jar") | .Vulnerabilities' trivy.json
```

For later images and both Linux architectures, see the JSON and SARIF artifacts
from the [image scan workflow](../.github/workflows/image-security-scan.yml).
