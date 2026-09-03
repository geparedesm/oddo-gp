import copy
import math
import re
from datetime import date, datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from odoo import fields
from odoo.exceptions import ValidationError


SOURCES = {
    "seek": "SEEK",
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
    "jora": "Jora",
    "company_careers": "Company Careers",
    "adzuna": "Adzuna",
    "greenhouse": "Greenhouse",
    "lever": "Lever",
    "ashby": "Ashby",
}
MODES = {"onsite", "hybrid", "remote"}
MODE_ALIASES = {
    "on-site": "onsite",
    "on site": "onsite",
    "office": "onsite",
    "in-office": "onsite",
    "hybrid": "hybrid",
    "remote": "remote",
    "remote-first": "remote",
}
TRACKING_PARAMETERS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "referrer", "source", "trk",
}
SENSITIVE_KEY = re.compile(r"(?:api[_-]?key|authorization|cookie|credential|password|secret|token)", re.I)
ALLOWED_PAYLOAD_KEYS = {
    "absolute_url", "categories", "company", "company_name", "companyName", "compensation",
    "content", "contract_time", "created", "createdAt", "currency", "date_found", "description",
    "descriptionPlain", "display_name", "hostedUrl", "id", "job_description", "job_url", "jobUrl",
    "location", "max", "metadata", "min", "modalidad", "name", "page", "page_size", "published_at", "publishedAt",
    "queried_at", "redirect_url", "result_limit",
    "salary_currency", "salary_min", "salary_max", "salaryRange", "text", "title", "updated_at",
    "work_mode", "workplaceType",
}


def canonical_url(value):
    """Return a deterministic HTTP(S) URL, preserving non-tracking query data."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Job URL must be a non-empty string.")
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError as error:
        raise ValidationError("Job URL is invalid.") from error
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValidationError("Job URL must use HTTP or HTTPS and include a valid host.")
    if any(character.isspace() for character in parts.netloc):
        raise ValidationError("Job URL host is invalid.")
    host = parts.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = "[%s]" % host
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if port is None or default_port else "%s:%s" % (host, port)
    query = sorted(
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), ""))


def _nested(payload, *path):
    value = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _provider_aliases(payload, source):
    aliases = {}
    if source == "adzuna":
        aliases = {
            "company": _nested(payload, "company", "display_name"),
            "location": _nested(payload, "location", "display_name"),
            "url": payload.get("redirect_url"),
            "source_job_id": payload.get("id"),
            # The country-specific AU endpoint reports salaries in AUD.
            "currency": payload.get("salary_currency") or (
                "AUD" if payload.get("salary_min") or payload.get("salary_max") else None
            ),
            "published_at": payload.get("created"),
        }
    elif source == "greenhouse":
        aliases = {
            "company": payload.get("company_name"),
            "location": _nested(payload, "location", "name"),
            "url": payload.get("absolute_url"),
            "description": payload.get("content"),
            "source_job_id": payload.get("id"),
            "published_at": payload.get("updated_at"),
            "work_mode": payload.get("work_mode") or _nested(payload, "metadata", "work_mode"),
        }
    elif source == "lever":
        aliases = {
            "title": payload.get("text"),
            "company": payload.get("company_name"),
            "location": _nested(payload, "categories", "location"),
            "url": payload.get("hostedUrl"),
            "description": payload.get("descriptionPlain"),
            "source_job_id": payload.get("id"),
            "salary_min": _nested(payload, "salaryRange", "min"),
            "salary_max": _nested(payload, "salaryRange", "max"),
            "currency": _nested(payload, "salaryRange", "currency"),
            "published_at": payload.get("createdAt"),
            "work_mode": payload.get("workplaceType"),
        }
    elif source == "ashby":
        aliases = {
            "company": payload.get("companyName"),
            "url": payload.get("jobUrl"),
            "description": payload.get("descriptionPlain"),
            "source_job_id": payload.get("id"),
            "salary_min": _nested(payload, "compensation", "min"),
            "salary_max": _nested(payload, "compensation", "max"),
            "currency": _nested(payload, "compensation", "currency"),
            "published_at": payload.get("publishedAt"),
            "work_mode": payload.get("workplaceType"),
        }
    return {key: value for key, value in aliases.items() if value is not None}


def _clean_payload(value, depth=0):
    if depth > 4:
        raise ValidationError("Source payload exceeds the supported nesting depth.")
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if not isinstance(key, str) or key not in ALLOWED_PAYLOAD_KEYS or SENSITIVE_KEY.search(key):
                continue
            cleaned[key] = _clean_payload(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_clean_payload(item, depth + 1) for item in value[:100]]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise ValidationError("Source payload contains an unsupported value type.")


def _required_text(value, label, maximum=10000):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("%s is required and must be text." % label)
    value = value.strip()
    if len(value) > maximum:
        raise ValidationError("%s exceeds the maximum supported length." % label)
    return value


def _source_identifier(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValidationError("Source job ID is required and must be text or an integer.")
    return _required_text(str(value), "Source job ID", 128)


def _salary(value, label):
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("%s must be numeric." % label)
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValidationError("%s must be a finite non-negative number." % label)
    return value


def _published_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, bool):
        raise ValidationError("Publication date is invalid.")
    if isinstance(value, (int, float)):
        try:
            seconds = value / 1000 if value > 100000000000 else value
            return datetime.fromtimestamp(seconds, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError) as error:
            raise ValidationError("Publication date is invalid.") from error
    if isinstance(value, str) and value.strip():
        candidate = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            try:
                return fields.Date.from_string(candidate)
            except (TypeError, ValueError) as error:
                raise ValidationError("Publication date must be an ISO date or datetime.") from error
    raise ValidationError("Publication date is required.")


def normalize_job(raw, source, provenance=None):
    """Validate and normalize any adapter result to the shared vacancy contract."""
    if not isinstance(raw, dict):
        raise ValidationError("Source payload must be a JSON object.")
    if source not in SOURCES:
        raise ValidationError("Unsupported vacancy source: %s." % source)
    payload = copy.deepcopy(raw)
    values = dict(payload)
    values.update(_provider_aliases(payload, source))
    title = _required_text(values.get("title") or values.get("name"), "Title", 512)
    company = _required_text(values.get("company") or values.get("company_name"), "Company", 512)
    location = _required_text(values.get("location"), "Location", 512)
    description = _required_text(
        values.get("description") or values.get("job_description"), "Description", 100000,
    )
    source_job_id = _source_identifier(values.get("source_job_id"))
    mode_value = values.get("work_mode") or values.get("modalidad")
    if mode_value in (None, ""):
        mode = False
    else:
        if not isinstance(mode_value, str):
            raise ValidationError("Work mode must be text when provided.")
        mode = MODE_ALIASES.get(mode_value.strip().casefold(), mode_value.strip().casefold())
        if mode not in MODES:
            raise ValidationError("Work mode must be onsite, hybrid, or remote.")
    salary_min = _salary(values.get("salary_min"), "Minimum salary")
    salary_max = _salary(values.get("salary_max"), "Maximum salary")
    if salary_min and salary_max and salary_min > salary_max:
        raise ValidationError("Minimum salary cannot exceed maximum salary.")
    currency_value = values.get("currency") or values.get("salary_currency")
    currency = currency_value.strip().upper() if isinstance(currency_value, str) else ""
    if (salary_min or salary_max) and not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValidationError("Salary currency must be a three-letter code when salary is provided.")
    if currency_value not in (None, "") and not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValidationError("Salary currency must be a three-letter code.")
    published = _published_date(values.get("published_at") or values.get("date_found"))
    safe_provenance = {
        "schema_version": 1,
        "provider": source,
        "original": _clean_payload(payload),
    }
    if provenance is not None:
        if not isinstance(provenance, dict):
            raise ValidationError("Provenance must be a JSON object.")
        allowed = {key: provenance[key] for key in ("queried_at", "page", "page_size", "result_limit") if key in provenance}
        safe_provenance.update(_clean_payload(allowed))
    return {
        "name": title,
        "company_name": company,
        "location": location,
        "job_url": canonical_url(values.get("url") or values.get("job_url")),
        "job_description": description,
        "source": source,
        "source_job_id": source_job_id,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency or False,
        "modalidad": mode,
        "date_found": fields.Date.to_string(published),
        "raw_job_data": safe_provenance,
    }
