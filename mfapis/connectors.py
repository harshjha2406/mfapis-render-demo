"""Three independent adapters; no synthetic market values."""
import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation

WB_URL = "https://api.worldbank.org/v2/country/IND;USA;GBR/indicator/NY.GDP.MKTP.KD.ZG"
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
TREASURY_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
ATTRIBUTIONS = {
    "worldbank": "World Bank, World Development Indicators. Normalized by MFAPIs. CC BY 4.0, subject to dataset terms.",
    "ecb": "Source: European Central Bank. Source data are available free at https://www.ecb.europa.eu/. Normalized by MFAPIs. Reference rates for information only.",
    "treasury": "Source: U.S. Department of the Treasury. Daily Treasury par yield curve rates. Normalized by MFAPIs.",
}


def row(source, entity, metric, day, value, unit, frequency, meta):
    d = date.fromisoformat(day)
    if d > date.today():
        raise ValueError("Future observation date")
    if not entity or not metric:
        raise ValueError("Missing identifier")
    if value is None or str(value).strip() in {"", "N/A", "null"}:
        number = None
    else:
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("Invalid numeric value") from exc
        if not number.is_finite():
            raise ValueError("Non-finite value")
        if source == "ecb" and number <= 0:
            raise ValueError("FX rates must be positive")
    return dict(source=source, entity=entity, metric=metric, observation_date=d,
                value=number, unit=unit, frequency=frequency,
                quality="missing" if number is None else "observed",
                source_url=meta["url"], raw_sha256=meta["sha256"],
                retrieved_at=meta["fetched_at"], attribution=ATTRIBUTIONS[source])


def worldbank_page(body, meta):
    payload = json.loads(body)
    if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[0], dict):
        raise ValueError("Unexpected World Bank schema / API error")
    if not isinstance(payload[1], list):
        raise ValueError("World Bank returned no observation list")
    out = []
    for x in payload[1]:
        country = x["countryiso3code"]
        if country not in {"IND", "USA", "GBR"}:
            raise ValueError("Unexpected country")
        if x["indicator"]["id"] != "NY.GDP.MKTP.KD.ZG":
            raise ValueError("Unexpected indicator")
        # Annual observation label is the year end; it is NOT the release date.
        out.append(row("worldbank", country, x["indicator"]["id"],
                       x["date"] + "-12-31", x["value"], "percent_yoy", "annual", meta))
    return payload[0], out


def ecb_rows(body, meta):
    root = ET.fromstring(body)
    out = []
    for cube in root.iter():
        if "time" not in cube.attrib:
            continue
        for item in cube:
            currency = item.attrib["currency"]
            if not re.fullmatch("[A-Z]{3}", currency):
                raise ValueError("Invalid currency code")
            out.append(row("ecb", "EUR/" + currency, "reference_rate", cube.attrib["time"],
                           item.attrib["rate"], currency + "_per_EUR", "daily", meta))
    if not out:
        raise ValueError("ECB response has no rates")
    return out


def treasury_rows(body, meta):
    root = ET.fromstring(body)
    out = []
    for props in root.iter():
        if props.tag.split("}")[-1] != "properties":
            continue
        fields = {x.tag.split("}")[-1]: x for x in props}
        day = fields["NEW_DATE"].text[:10]
        for name, item in fields.items():
            match = re.fullmatch(r"BC_(\d+)(MONTH|YEAR)", name)
            if not match:
                continue
            tenor = match[1] + ("M" if match[2] == "MONTH" else "Y")
            value = None if any(k.endswith("}null") and v == "true" for k, v in item.attrib.items()) else item.text
            out.append(row("treasury", "US_TREASURY", "par_yield_" + tenor, day,
                           value, "percent_per_year", "daily", meta))
    if not out:
        raise ValueError("Treasury response has no curve observations")
    return out


def extract(source, fetcher, start, end):
    if source == "worldbank":
        # Do not request the current/incomplete annual period: the provider can
        # return null placeholders whose year-end label is still in the future.
        last_year = end.year if (end.month, end.day) == (12, 31) else end.year - 1
        if last_year < start.year:
            return
        page, expected = 1, None
        while True:
            body, meta = fetcher.get(source, WB_URL, {"format": "json", "date": f"{start.year}:{last_year}", "per_page": 100, "page": page})
            info, rows = worldbank_page(body, meta)
            pages = int(info["pages"])
            if pages < 1 or pages > 1000 or int(info["page"]) != page:
                raise ValueError("Invalid World Bank pagination")
            if expected is not None and expected != pages:
                raise ValueError("Pagination changed mid-run; retry")
            expected = pages
            yield from (r for r in rows if start <= r["observation_date"] <= end)
            if page >= pages:
                break
            page += 1
    elif source == "ecb":
        # The static source cannot be server-filtered; always archive full response.
        body, meta = fetcher.get(source, ECB_URL)
        yield from (r for r in ecb_rows(body, meta) if start <= r["observation_date"] <= end)
    elif source == "treasury":
        for year in range(start.year, end.year + 1):
            body, meta = fetcher.get(source, TREASURY_URL,
                                    {"data": "daily_treasury_yield_curve", "field_tdr_date_value": year})
            yield from (r for r in treasury_rows(body, meta) if start <= r["observation_date"] <= end)
    else:
        raise ValueError("Unknown source")
