"""Synthetic source batches; this is our own contract, not an actual API schema."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from .classification import input_dict, parse_classification_input
from .models import DemoDataError, _items, _object, _read, _text, opportunity_dict, parse_opportunity


SOURCES = frozenset({"doffin", "mercell"})


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    return hashlib.sha256(json_text(value).encode("utf-8")).hexdigest()


def timestamp(value: object, field: str) -> str:
    raw = _text(value, field)
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DemoDataError(f"{field}: forventet dato og klokkeslett med tidssone.") from exc
    if result.tzinfo is None:
        raise DemoDataError(f"{field}: tidssone må være oppgitt.")
    return result.astimezone(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class SourceRecord:
    source: str
    record_id: str
    competition_ref: str | None
    modified_at: str
    payload: dict

    @property
    def fingerprint(self) -> str:
        return digest({"competition_ref": self.competition_ref, "payload": self.payload})


@dataclass(frozen=True)
class SourceBatch:
    id: str
    fingerprint: str
    read_until: dict[str, str]
    records: tuple[SourceRecord, ...]


def parse_source_batch(data: dict) -> SourceBatch:
    data = _object(data, "batch")
    if data.get("synthetic") is not True:
        raise DemoDataError("Kildebatchen må være merket synthetic=true.")
    batch_id = _text(data.get("batch_id"), "batch_id")
    preparation = data.get("preparation", "prepared_demo")
    if not isinstance(preparation, str) or preparation not in {"prepared_demo", "rules"}:
        raise DemoDataError("preparation må være prepared_demo eller rules.")
    read_until = {}
    for source, through in _object(data.get("read_until"), "read_until").items():
        if source not in SOURCES:
            raise DemoDataError(f"Ukjent demokilde: {source}.")
        read_until[source] = timestamp(through, "read_until")
    if not read_until:
        raise DemoDataError("read_until må oppgi minst én kilde.")
    records, seen = [], set()
    for raw in _items(data.get("records"), "records"):
        row = _object(raw, "source record")
        source = _text(row.get("source"), "source")
        if source not in read_until:
            raise DemoDataError(f"Kilden {source} mangler en lesegrense i read_until.")
        record_id = _text(row.get("record_id"), "record_id")
        if (source, record_id) in seen:
            raise DemoDataError("Samme kilde-ID forekommer flere ganger i én batch.")
        seen.add((source, record_id))
        modified_at = timestamp(row.get("modified_at"), "modified_at")
        if modified_at > read_until[source]:
            raise DemoDataError("En kildepost er nyere enn batchens oppgitte lesegrense.")
        content = _object(row.get("opportunity"), "opportunity")
        if preparation == "rules" and any(content.get(field) for field in ("main_trade", "other_trades", "area")):
            raise DemoDataError("I rules-modus skal fag og område beregnes fra regler, ikke settes manuelt.")
        prepared = parse_opportunity({**content, "id": f"{source}:{record_id}"})
        payload = opportunity_dict(prepared)
        payload.pop("id")
        payload["description"] = _text(content.get("description"), "description", True)
        urls = []
        for item in _items(content.get("document_urls", []), "document_urls"):
            url = _text(item, "document_url")
            parsed = urlsplit(url)
            if parsed.scheme not in {"https", "http"} or not parsed.netloc:
                raise DemoDataError("Dokumentlenker må være HTTP- eller HTTPS-adresser.")
            if url not in urls:
                urls.append(url)
        payload["document_urls"] = urls
        status = content.get("notice_status")
        if status not in (None, "active", "cancelled"):
            raise DemoDataError("notice_status må være active, cancelled eller null.")
        payload["notice_status"] = status
        if preparation == "rules":
            payload["classification_input"] = input_dict(parse_classification_input({
                **content, "id": f"{source}:{record_id}",
            }))
        records.append(SourceRecord(source, record_id,
                                    _text(row.get("competition_ref"), "competition_ref", True),
                                    modified_at, payload))
    return SourceBatch(batch_id, digest(data), read_until, tuple(records))


def load_source_batch(path: Path) -> SourceBatch:
    return parse_source_batch(_read(path))
