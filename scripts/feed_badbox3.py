"""Parse network indicators from HUMAN Security's BADBOX 3.0 tables."""

import ipaddress
import re
from html.parser import HTMLParser


SECTION = "Indicators of Compromise (IOCs)"
MINIMUM_ROWS = {
    "Command-and-control and payload hosting": 7,
    "Ad fraud infrastructure": 8,
    "PXYEDGE infrastructure": 18,
}

ROLE_PREFIXES = {
    "module list and logging": "C2, каталог модулей и приём журналов",
    "operator-controlled payload host": "Загрузка компонентов с сервера операторов",
    "self-hosted github proxy": "Прокси операторов для загрузки компонентов",
    "parent domain": "Родительский домен инфраструктуры C2",
    "module c2": "C2 модулей",
    "legacy c2": "Прежний сервер C2",
    "ad behavior management": "Управление показом рекламы",
    "module downloader c2": "C2 загрузчика модулей",
    "ad fraud and tasking c2": "C2 рекламного мошенничества и выдачи заданий",
    "cloud storage endpoint": "Облачное хранилище для модулей рекламного мошенничества",
    "serves hidden ad configurations": "Конфигурации скрытой рекламы и ссылки загрузки APK",
    "storefront domain": "Витрина прокси-сети PXYEDGE",
    "command server": "Сервер управления прокси-сетью PXYEDGE",
    "relay (data plane)": "Ретранслятор прокси-сети PXYEDGE",
    "database/state server": "Сервер базы данных и состояния PXYEDGE",
    "proxy role": "Прокси PXYEDGE, ранее сервер заданий BADBOX",
    "message queue": "Сервер очереди сообщений PXYEDGE",
    "frontend, api, and management": "Веб-интерфейс, API и управление PXYEDGE",
    "myic server": "Сервер прокси-сети myic",
}

HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


class IocTables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.section_seen = False
        self.in_section = False
        self.heading = None
        self.heading_parts = []
        self.table_name = None
        self.tables = {}
        self.in_table = False
        self.row = None
        self.cell = None
        self.cell_parts = []

    def handle_starttag(self, tag, attrs):
        if not self.in_table and tag in {"h1", "h2", "h3", "h4"}:
            self.heading = tag
            self.heading_parts = []
        if not self.in_section:
            return
        if tag == "table":
            if self.in_table or self.table_name is None or self.table_name in self.tables:
                raise ValueError("BADBOX 3.0: unexpected table in IOC section")
            self.in_table = True
            self.tables[self.table_name] = []
        elif self.in_table and tag == "tr":
            if self.row is not None:
                raise ValueError(f"BADBOX 3.0: unclosed row in {self.table_name}")
            self.row = []
        elif self.in_table and tag in {"th", "td"}:
            attributes = dict(attrs)
            if (
                self.row is None
                or self.cell is not None
                or attributes.get("rowspan", "1") != "1"
                or attributes.get("colspan", "1") != "1"
            ):
                raise ValueError(f"BADBOX 3.0: unexpected cell in {self.table_name}")
            self.cell = tag
            self.cell_parts = []

    def handle_endtag(self, tag):
        if tag == self.heading:
            title = " ".join("".join(self.heading_parts).split())
            self.heading = None
            if tag == "h3" and title == SECTION:
                if self.section_seen:
                    raise ValueError("BADBOX 3.0: repeated IOC section")
                self.section_seen = True
                self.in_section = True
            elif tag in {"h1", "h2", "h3"}:
                self.in_section = False
            elif self.in_section:
                if title not in MINIMUM_ROWS:
                    raise ValueError(f"BADBOX 3.0: unrecognized IOC subsection {title!r}")
                self.table_name = title
        if not self.in_table:
            return
        if tag in {"th", "td"}:
            if tag != self.cell:
                raise ValueError(f"BADBOX 3.0: mismatched cell tag in {self.table_name}")
            self.row.append((tag, " ".join("".join(self.cell_parts).split())))
            self.cell = None
        elif tag == "tr":
            if self.row is None or self.cell is not None:
                raise ValueError(f"BADBOX 3.0: incomplete row in {self.table_name}")
            self.tables[self.table_name].append(self.row)
            self.row = None
        elif tag == "table":
            if self.row is not None:
                raise ValueError(f"BADBOX 3.0: incomplete table {self.table_name}")
            self.in_table = False

    def handle_data(self, data):
        if self.heading is not None:
            self.heading_parts.append(data)
        if self.cell is not None:
            self.cell_parts.append(data)


def normalize_indicator(value):
    address = value.lower().replace("[.]", ".")
    port = None
    bracketed = re.fullmatch(r"\[([0-9a-f:.]+)\]:([0-9]{1,5})", address)
    if bracketed:
        address, port = bracketed.groups()
    elif address.count(":") == 1:
        address, port = address.rsplit(":", 1)
    if port is not None and (re.fullmatch(r"[0-9]{1,5}", port) is None or not 1 <= int(port) <= 65535):
        raise ValueError(f"BADBOX 3.0: invalid port in {value!r}")

    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        if (
            bracketed
            or len(address) > 253
            or "." not in address
            or not all(HOST_LABEL.fullmatch(label) for label in address.split("."))
            or address.rsplit(".", 1)[1].isdigit()
        ):
            raise ValueError(f"BADBOX 3.0: expected a literal IOC host or IP, got {value!r}") from None
        return address, "domain", "full", port

    if not ip.is_global or ip.is_multicast or "%" in address:
        raise ValueError(f"BADBOX 3.0: expected a public unicast IP, got {value!r}")
    return f"{ip}/{ip.max_prefixlen}", "ip", "ip", port


def parse(html: str) -> list[dict]:
    parser = IocTables()
    parser.feed(html)
    parser.close()
    if parser.in_table or parser.tables.keys() != MINIMUM_ROWS.keys():
        raise ValueError("BADBOX 3.0: missing or incomplete IOC tables")

    records = []
    for title, minimum in MINIMUM_ROWS.items():
        rows = parser.tables[title]
        if not rows or rows[0] != [("th", "Indicator"), ("th", "Role")]:
            raise ValueError(f"BADBOX 3.0: header changed in {title}")
        seen = set()
        for row in rows[1:]:
            if len(row) != 2 or any(tag != "td" for tag, _ in row):
                raise ValueError(f"BADBOX 3.0: IOC row shape changed in {title}")
            value, original_role = [cell[1] for cell in row]
            indicator, kind, match, port = normalize_indicator(value)
            role = next(
                (role for prefix, role in ROLE_PREFIXES.items() if original_role.lower().startswith(prefix)),
                None,
            )
            if role is None:
                raise ValueError(f"BADBOX 3.0: unrecognized IOC role for {value!r} in {title}")
            if port:
                role = f"{role} (порт {port} в источнике)"
            seen.add(indicator)
            record = {"indicator": indicator, "kind": kind, "match": match, "role": role}
            if port and kind == "ip":
                record["port"] = int(port)
            records.append(record)
        if len(seen) < minimum:
            raise ValueError(f"BADBOX 3.0: {title} has {len(seen)} distinct IOCs, expected at least {minimum}")
    return records
