# BADBOX Geodata

[![Geodata build](https://github.com/zeffbtw/badbox-geodata/actions/workflows/geodata.yml/badge.svg?branch=main)](https://github.com/zeffbtw/badbox-geodata/actions/workflows/geodata.yml)

Domain and IP blocklists for Xray and Remnawave. The lists cover published indicators associated with BADBOX, BADBOX 2.0, and BADBOX 3.0. They can be used alongside Chocolate4U’s `security.dat` and `security-ip.dat`.

## Downloads

| List | Download | Xray rule |
| --- | --- | --- |
| Domains (GeoSite) | [badbox.dat](https://raw.githubusercontent.com/zeffbtw/badbox-geodata/main/dist/badbox.dat) | `ext:badbox.dat:badbox` |
| IP networks (GeoIP) | [badbox-ip.dat](https://raw.githubusercontent.com/zeffbtw/badbox-geodata/main/dist/badbox-ip.dat) | `ext:badbox-ip.dat:badbox` |

[SHA-256 checksums](dist/SHA256SUMS) · [Build report](dist/report.json) · [Update history](https://github.com/zeffbtw/badbox-geodata/commits/main/dist)

## Quick start

- **Xray.** Place both DAT files in your Xray assets directory. Add separate `domain` and `ip` rules to `routing.rules` using the expressions above. Place them above any rules that would otherwise allow the traffic, and point them to a `blackhole` outbound. [Example routing rules](snippets/BADBOX-RULES.json)
- **Remnawave.** Add the two BADBOX assets to your geodata snippet and include it in the profile’s top-level `snippets` array. Create the `BADBOX-RULES` snippet from the example and set your block outbound tag in both rules. Insert `{"snippet": "BADBOX-RULES"}` before any matching allow rules in `routing.rules`. The node downloads missing files at startup. The example schedule refreshes them on Mondays at 02:30 in the container’s time zone. [Geodata snippet](snippets/GEODATA.json) · [Detailed setup and rollback (Russian)](snippets/README.md)

## Updates

GitHub Actions checks the upstream sources daily at **04:17 UTC**. GitHub can delay scheduled runs. You can also select **Run workflow** to check immediately, and changes to the build or its inputs on `main` trigger a check. [Workflow runs](https://github.com/zeffbtw/badbox-geodata/actions/workflows/geodata.yml)

Each run’s **Summary** shows the previous and current counts of domain and IP/CIDR rules, additions, removals, and domain match type changes. The update commit includes the same counts.

The workflow tests both DAT files with Xray before publishing them in one commit with the checksums and build report. When the inputs are unchanged, the workflow records a successful check in Actions. A failed check leaves the last published version available.

## Sources

| Variant | Coverage and refresh |
| --- | --- |
| BADBOX | Command-and-control and delivery infrastructure, including PEACHPIT C2. The workflow checks the PDF appendix daily. [HUMAN report](https://www.humansecurity.com/hubfs/HUMAN_Report_BADBOX-and-PEACHPIT.pdf) · [Bitsight research](https://www.bitsight.com/blog/badbox-botnet-back) |
| BADBOX 2.0 | C2, delivery and proxy hosts, and Hidden WebViews/H5 ad-fraud domains. The workflow checks the H5 CSV daily. [HUMAN research](https://www.humansecurity.com/learn/blog/satori-threat-intelligence-disruption-badbox-2-0/) · [H5 CSV](https://www.humansecurity.com/wp-content/uploads/2025/03/BADBOX-2-H5-Domain-List.csv) |
| BADBOX 3.0 | C2, delivery, ad-fraud, and PXYEDGE indicators. The parser uses a saved copy of the research page. [HUMAN research](https://www.humansecurity.com/learn/blog/satori-threat-intelligence-disruption-badbox-3-0-hides-the-largest-ad-fraud-operation-ever-disclosed-inside-infected-tv-boxes/) |

A `full` rule matches the exact hostname. A `domain` rule also matches subdomains. The source files document the evidence behind each rule and the reasons for exclusions. [Source data](data/)

<details>
<summary>Build and verify locally</summary>

Use Python 3.11+, `curl`, Poppler’s `pdftotext`, and Xray v26.11.9.

```sh
python3 scripts/refresh.py
python3 scripts/build.py --xray /path/to/xray
(cd dist && shasum -a 256 -c SHA256SUMS)
```

To recheck BADBOX 3.0, save the research page as `human-badbox3.html` and run `python3 scripts/refresh.py --snapshot-dir /path/to/snapshots`.

To verify or roll back a specific build, download both DAT files and the checksums from the same commit SHA.

</details>
