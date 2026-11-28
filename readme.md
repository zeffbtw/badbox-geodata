# BADBOX Geodata

[![Geodata build](https://github.com/zeffbtw/badbox-geodata/actions/workflows/geodata.yml/badge.svg?branch=main)](https://github.com/zeffbtw/badbox-geodata/actions/workflows/geodata.yml)

Domain and IP blocklists for Xray and Remnawave. The core rules cover published infrastructure for BADBOX, BADBOX 2.0, and BADBOX 3.0, including historical command-and-control and payload hosts. They can be used alongside Chocolate4U’s `security.dat` and `security-ip.dat`.

## Downloads

| List | Download | Xray rule |
| --- | --- | --- |
| Domains (GeoSite) | [badbox.dat](https://raw.githubusercontent.com/zeffbtw/badbox-geodata/main/dist/badbox.dat) | `ext:badbox.dat:badbox` |
| IP networks (GeoIP) | [badbox-ip.dat](https://raw.githubusercontent.com/zeffbtw/badbox-geodata/main/dist/badbox-ip.dat) | `ext:badbox-ip.dat:badbox` |
| Optional H5 ad-fraud sites | [badbox-h5.dat](https://raw.githubusercontent.com/zeffbtw/badbox-geodata/main/dist/badbox-h5.dat) | `ext:badbox-h5.dat:badbox` |

[SHA-256 checksums](dist/SHA256SUMS) · [Build report](dist/report.json) · [Update history](https://github.com/zeffbtw/badbox-geodata/commits/main/dist)

## Quick start

- **Xray.** Place the two core DAT files in your Xray assets directory. Copy the routing rules into `routing.rules` above any matching allow rules and set their outbound tag to your `blackhole` outbound. [Example routing rules](snippets/BADBOX-RULES.json)
- **Remnawave.** Add the two core BADBOX assets to your geodata snippet and include it in the profile’s top-level `snippets` array. Create `BADBOX-RULES` from the example and set the outbound tag in every rule. Insert `{"snippet": "BADBOX-RULES"}` before any matching allow rules. The node downloads missing files at startup. The example schedule refreshes them on Mondays at 02:30 in the container’s time zone. [Geodata snippet](snippets/GEODATA.json) · [Detailed setup and rollback (Russian)](snippets/README.md)

Update existing copies of `BADBOX-RULES` when adopting this build. The snippet contains `ip` and `port` rules for endpoints reported with specific ports. The GeoIP DAT stores address-only rules. [Routing snippet](snippets/BADBOX-RULES.json)

The optional H5 list covers sites used by the BADBOX 2.0 hidden-browser ad-fraud scheme. To enable it, add the H5 asset to `geodata.assets` and install the `BADBOX-H5-RULES` snippet. [Asset JSON](snippets/BADBOX-H5-ASSET.json) · [Rule JSON](snippets/BADBOX-H5-RULES.json) · [Remnawave setup](snippets/README.md#подключение-h5)

## Updates

GitHub Actions checks Nokia Deepfield’s MoYu C2 CSV every Sunday at **04:17 UTC**. GitHub can delay scheduled runs. You can also select **Run workflow** to check immediately. Changes to the build or its inputs on `main` trigger a check. Previously observed C2 hosts remain in the evidence when the upstream table rotates. [Workflow runs](https://github.com/zeffbtw/badbox-geodata/actions/workflows/geodata.yml)

Each run’s **Summary** shows counts and changes for the core domains, IP/CIDR rules, optional H5 domains, and IP and port pairs. The update commit includes the same counts.

The workflow tests the DAT files and routing rules with Xray before publishing the build with its checksums and report. When the inputs are unchanged, the workflow records a successful check in Actions. A failed check leaves the last published version available.

## Sources

| Variant | Coverage and refresh |
| --- | --- |
| BADBOX | Historical C2 and payload delivery, including PEACHPIT. Early reports are corroborated by T95 firmware and traffic analysis. [HUMAN PDF](https://www.humansecurity.com/hubfs/HUMAN_Report_BADBOX-and-PEACHPIT.pdf) · [Bitsight](https://www.bitsight.com/blog/badbox-botnet-back) · [DesktopECHO](https://github.com/DesktopECHO/T95-H616-Malware) |
| BADBOX 2.0 | C2, delivery and proxy infrastructure. Nokia’s exact `a1.` and `t1.` C2 hosts refresh automatically. Reviewed records include MoYu and Bird backdoor indicators from Google GTIG and a MoYu plugin catalog from Synthient. [HUMAN](https://www.humansecurity.com/learn/blog/satori-threat-intelligence-disruption-badbox-2-0/#list-of-c2-domains) · [Nokia Deepfield](https://github.com/deepfield/public-research/tree/main/ipmoyu/iocs) · [Kaspersky](https://securelist.com/android-head-unit-malware/121106/#indicators-of-compromise) · [Google GTIG](https://cloud.google.com/blog/topics/threat-intelligence/shutting-the-door-on-the-xcpe-botnet#indicators-of-compromise) |
| BADBOX 3.0 | C2, delivery, ad-fraud and PXYEDGE indicators. Synthient’s Nexus firmware analysis corroborates two module endpoints in the HUMAN report. [HUMAN](https://www.humansecurity.com/learn/blog/satori-threat-intelligence-disruption-badbox-3-0-hides-the-largest-ad-fraud-operation-ever-disclosed-inside-infected-tv-boxes/#indicators-of-compromise-iocs) · [Synthient](https://github.com/synthient/public-research/blob/main/2026/11/Videostrong/README.md) |

A `full` rule matches the exact hostname. A `domain` rule also matches subdomains. The source files document the evidence behind each rule and the reasons for exclusions. [Source data](data/)

<details>
<summary>Build and verify locally</summary>

Use Python 3.11+, `curl`, and Xray v26.11.9. Rechecking a saved PDF also requires Poppler’s `pdftotext`.

```sh
python3 scripts/refresh.py
python3 scripts/build.py --xray /path/to/xray
(cd dist && shasum -a 256 -c SHA256SUMS)
```

To recheck BADBOX 3.0, save the research page as `human-badbox3.html` and run `python3 scripts/refresh.py --snapshot-dir /path/to/snapshots`.

To verify or roll back a specific build, use its DAT files, routing snippet and checksums from the same commit SHA.

</details>
