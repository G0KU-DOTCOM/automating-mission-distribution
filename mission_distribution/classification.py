"""Explainable CPV/keyword baseline and synthetic municipality-area lookup."""

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path

from .models import DemoDataError, TRADES, _items, _object, _read, _text, _trade


def cpv_code(value: object, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    raw = _text(value, "CPV-kode")
    if not re.fullmatch(r"[0-9]{8}(?:-[0-9])?", raw):
        raise DemoDataError("CPV-kode må ha åtte sifre, eventuelt med en kontrollsiffer-del som -2.")
    # Format validation only; membership and check digits are not verified against an official register.
    return raw.split("-")[0]


def _normal_text(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


def _contains(text: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(_normal_text(phrase)) + r"(?!\w)", text) is not None


@dataclass(frozen=True)
class CpvRule:
    prefix: str
    trade: str


@dataclass(frozen=True)
class KeywordRule:
    phrase: str
    trade: str


@dataclass(frozen=True)
class ClassificationRules:
    cpv_rules: tuple[CpvRule, ...]
    keyword_rules: tuple[KeywordRule, ...]
    excluded_codes: frozenset[str]
    broad_codes: frozenset[str]
    trade_priority: tuple[str, ...]
    municipality_areas: dict[str, str]
    brand_words: tuple[str, ...]
    type_prefixes: dict[str, tuple[str, ...]]
    fingerprint: str


@dataclass(frozen=True)
class ClassificationInput:
    id: str
    title: str
    description: str | None
    main_cpv: str | None
    additional_cpvs: tuple[str, ...]
    delivery_municipalities: tuple[str, ...]
    buyer_municipality: str | None
    notice_kind: str


def parse_classification_input(raw: dict) -> ClassificationInput:
    data = _object(raw, "classification input")
    title = _text(data.get("title"), "title")
    additional = tuple(dict.fromkeys(cpv_code(code) for code in _items(data.get("additional_cpvs", []), "additional_cpvs")))
    municipalities = tuple(dict.fromkeys(_text(code, "delivery_municipality")
                                         for code in _items(data.get("delivery_municipalities", []), "delivery_municipalities")))
    kind = data.get("notice_kind", "competition")
    if not isinstance(kind, str) or kind not in {"competition", "prior_information", "market_dialogue"}:
        raise DemoDataError("notice_kind må være competition, prior_information eller market_dialogue.")
    return ClassificationInput(
        _text(data.get("id"), "id"), title, _text(data.get("description"), "description", True),
        cpv_code(data.get("main_cpv"), True), additional, municipalities,
        _text(data.get("buyer_municipality"), "buyer_municipality", True), kind,
    )


def input_dict(value: ClassificationInput) -> dict:
    return {"id": value.id, "title": value.title, "description": value.description,
            "main_cpv": value.main_cpv, "additional_cpvs": list(value.additional_cpvs),
            "delivery_municipalities": list(value.delivery_municipalities),
            "buyer_municipality": value.buyer_municipality, "notice_kind": value.notice_kind}


def load_classification_rules(path: Path) -> ClassificationRules:
    data = _read(path)
    cpvs, keywords, seen_prefixes, seen_keywords = [], [], set(), set()
    for raw in _items(data.get("cpv_rules"), "cpv_rules"):
        row = _object(raw, "cpv_rule")
        prefix = _text(row.get("prefix"), "cpv prefix")
        if not re.fullmatch(r"[0-9]{2,8}", prefix) or prefix in seen_prefixes:
            raise DemoDataError("CPV-prefikser må ha 2–8 sifre og være unike.")
        seen_prefixes.add(prefix)
        cpvs.append(CpvRule(prefix, _trade(row.get("trade"))))
    for raw in _items(data.get("keyword_rules"), "keyword_rules"):
        row = _object(raw, "keyword_rule")
        phrase = _text(row.get("phrase"), "keyword")
        key = _normal_text(phrase)
        if not key or key in seen_keywords:
            raise DemoDataError("Nøkkelord må ha innhold og være unike etter normalisering.")
        seen_keywords.add(key)
        keywords.append(KeywordRule(phrase, _trade(row.get("trade"))))
    excluded = frozenset(cpv_code(code) for code in _items(data.get("excluded_codes"), "excluded_codes"))
    broad = frozenset(cpv_code(code) for code in _items(data.get("broad_codes"), "broad_codes"))
    if excluded & broad:
        raise DemoDataError("En kode kan ikke være både ekskludert og en bred kode for avklaring.")
    priority = tuple(_trade(trade) for trade in _items(data.get("trade_priority"), "trade_priority"))
    if len(priority) != len(TRADES) or set(priority) != TRADES:
        raise DemoDataError("Fagprioriteten må inneholde BA, FS og SE én gang hver.")
    areas = {_text(code, "municipality code"): _text(area, "area")
             for code, area in _object(data.get("municipality_areas"), "municipality_areas").items()}
    brands = tuple(_text(word, "brand word") for word in _items(data.get("brand_words"), "brand_words"))
    normalized_brands = [_normal_text(word) for word in brands]
    if any(not word for word in normalized_brands) or len(set(normalized_brands)) != len(normalized_brands):
        raise DemoDataError("Merkenavn må ha innhold og være unike etter normalisering.")
    types, prefixes = {}, set()
    for name, values in _object(data.get("type_prefixes"), "type_prefixes").items():
        if name not in {"installasjon", "leveranse", "service"}:
            raise DemoDataError("Ukjent oppdragstype i type_prefixes.")
        types[name] = tuple(_text(prefix, "type prefix") for prefix in _items(values, "type prefixes"))
        for prefix in types[name]:
            if not re.fullmatch(r"[0-9]{2,8}", prefix) or prefix in prefixes:
                raise DemoDataError("Typeprefikser må ha 2–8 sifre og være unike.")
            prefixes.add(prefix)
    fingerprint = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")).encode("utf-8")).hexdigest()
    return ClassificationRules(tuple(cpvs), tuple(keywords), excluded, broad, priority, areas,
                               brands, types, fingerprint)


def _area(value: ClassificationInput, rules: ClassificationRules) -> tuple[str | None, str, bool]:
    if not value.delivery_municipalities:
        area = rules.municipality_areas.get(value.buyer_municipality)
        return area, ("Leveringssted mangler; området er hentet fra innkjøpers demokommune."
                      if area else "Verken leveringssted eller innkjøpers demokommune gir et kjent område."), False
    unknown = [code for code in value.delivery_municipalities if code not in rules.municipality_areas]
    areas = {rules.municipality_areas[code] for code in value.delivery_municipalities if code in rules.municipality_areas}
    if unknown:
        return None, "Minst ett leveringssted mangler kobling i områdetabellen. Området må avklares.", len(areas) > 1
    if len(areas) > 1:
        area = rules.municipality_areas.get(value.buyer_municipality)
        return area, ("Flere leveringsområder; innkjøpers demokommune brukes som område."
                      if area else "Flere leveringsområder, men innkjøpers demokommune gir ikke et kjent område."), True
    return next(iter(areas)), "Området er hentet fra leveringsstedets demokommune.", False


def classify(value: ClassificationInput, rules: ClassificationRules) -> dict:
    texts = {"title": _normal_text(value.title), "description": _normal_text(value.description or "")}
    hits, excluded, broad, detected = [], [], [], set()
    main_trade = None
    for role, code in [("main", value.main_cpv)] + [("additional", code) for code in value.additional_cpvs]:
        if code is None:
            continue
        if code in rules.excluded_codes:
            excluded.append(code)
            continue
        if code in rules.broad_codes:
            broad.append(code)
            continue
        matches = [rule for rule in rules.cpv_rules if code.startswith(rule.prefix)]
        if matches:
            selected = max(matches, key=lambda rule: len(rule.prefix))
            detected.add(selected.trade)
            hits.append({"kind": "cpv", "code": code, "role": role,
                         "matched_prefix": selected.prefix, "trade": selected.trade})
            if role == "main":
                main_trade = selected.trade
    for rule in rules.keyword_rules:
        fields = [field for field, text in texts.items() if _contains(text, rule.phrase)]
        if fields:
            detected.add(rule.trade)
            hits.append({"kind": "keyword", "phrase": rule.phrase, "trade": rule.trade, "fields": fields})
    trades = [trade for trade in rules.trade_priority if trade in detected]
    if trades:
        relevance = "relevant"
        basis = "hoved_cpv" if main_trade else "fagprioritet"
        main_trade = main_trade or trades[0]
        explanation = ("Hoved-CPV-koden bestemmer hovedfaget; øvrige treff beholdes."
                       if basis == "hoved_cpv" else "Relevante treff er funnet. Hovedfaget velges etter demoens fagprioritet.")
    elif broad:
        relevance, basis = "fag_ukjent", "bred_cpv"
        explanation = "Bare brede CPV-koder gir treff. Oppdraget går videre med ukjent fag."
    else:
        relevance, basis = "ikke_relevant", "ingen_treff"
        explanation = "Ingen relevante CPV- eller nøkkelordtreff i tilgjengelig tekst. Bortsortert etter demoreglene."
    area, area_explanation, multiple = _area(value, rules)
    brands = [word for word in rules.brand_words if any(_contains(text, word) for text in texts.values())]
    flags = []
    if brands:
        flags.append("MERKENAVN")
    if value.notice_kind in {"prior_information", "market_dialogue"}:
        flags.append("TIDLIG_FASE")
    if multiple:
        flags.append("FLERE_OMRÅDER")
    type_matches = [(len(prefix), name) for name, prefixes in rules.type_prefixes.items()
                    for prefix in prefixes if value.main_cpv and value.main_cpv.startswith(prefix)]
    work_type = max(type_matches)[1] if type_matches else "ukjent"
    return {
        "id": value.id, "method": "cpv_og_nokkelord", "rules_fingerprint": rules.fingerprint,
        "relevance": relevance, "should_route": relevance != "ikke_relevant", "main_trade": main_trade,
        "other_trades": [trade for trade in trades if trade != main_trade], "work_type": work_type,
        "main_trade_basis": basis, "explanation": explanation, "hits": hits,
        "excluded_codes": list(dict.fromkeys(excluded)), "broad_codes": list(dict.fromkeys(broad)),
        "area": area, "area_explanation": area_explanation, "brand_hits": brands, "public_flags": flags,
    }


def load_classification_cases(path: Path) -> list[ClassificationInput]:
    data = _read(path)
    cases, ids = [], set()
    for raw in _items(data.get("cases"), "cases"):
        case = parse_classification_input(raw)
        if case.id in ids:
            raise DemoDataError("Eksempelsakene for klassifisering må ha unike ID-er.")
        ids.add(case.id)
        cases.append(case)
    return cases
