"""Sparse, deterministic politics. No economy or player book is mutated here.

Political bond pricing is deliberately disabled until coherent coarse bond,
curve, fund and derivative consumption passes its separate release gate.
"""
from __future__ import annotations

import calendar
import hashlib
import itertools
import math
import random
from copy import deepcopy
from datetime import date, datetime, timedelta

MODEL_VERSION = 1
CALIBRATION_VERSION = 1
PREMIUM_ENABLED = False
SYSTEMS = {
    "parliamentary_democracy": ("Parliamentary Democracy", 4, True),
    "presidential_democracy": ("Presidential Democracy", 4, True),
    "semi_presidential_democracy": ("Semi-Presidential Democracy", 5, True),
    "constitutional_monarchy": ("Constitutional Monarchy", 4, True),
    "absolute_monarchy": ("Absolute Monarchy", 0, False),
    "one_party_state": ("One-Party State", 5, False),
    "authoritarian_republic": ("Authoritarian Republic", 5, False),
}
PARLIAMENTARY = {"parliamentary_democracy", "constitutional_monarchy", "semi_presidential_democracy"}
NAME_WORDS = ("Civic", "Liberal", "Conservative", "Social", "Labor", "Reform", "Democratic", "National", "Progressive")
NAME_ENDINGS = ("Alliance", "Union", "Movement", "Party")


def day(value):
    return value.date() if isinstance(value, datetime) else value


def add_years(value: date, years: int) -> date:
    year = value.year + years
    return value.replace(year=year, day=min(value.day, calendar.monthrange(year, value.month)[1]))


def rng(seed, country, stream):
    token = f"politics:{MODEL_VERSION}:{seed}:{country}:{stream}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(token).digest(), "big"))


def normalize(values):
    total = math.fsum(values)
    shares = [v / total for v in values]
    shares[-1] = 1.0 - sum(shares[:-1])
    return shares


def macro_snapshot(macro):
    return {key: float(macro.get(field, default)) for key, field, default in (
        ("growth", "bip_prozent", .015), ("unemployment", "arbeitslosigkeit", .052),
        ("inflation", "inflation", .02))}


def form_government(p, shares=None):
    """Search at most 127 subsets; support is an explicit V1 mandate abstraction."""
    parties = sorted(p["parties"], key=lambda item: item["id"])
    values = shares or {a["id"]: a["mandate_share"] for a in parties}
    if not parties:
        return [], [], "continuity", None
    winner = min(parties, key=lambda a: (-values[a["id"]], a["id"]))["id"]
    if p["system"] == "one_party_state":
        return [winner], [], "one_party_government", None
    if p["system"] == "presidential_democracy":
        return [winner], [], "plurality_executive", winner
    executive = winner if p["system"] == "semi_presidential_democracy" else None
    previous = set(p.get("government_ids", []))
    candidates = []
    for count in range(1, len(parties) + 1):
        for subset in itertools.combinations(parties, count):
            axes = [a["economic_axis"] for a in subset]
            distance = (max(axes) - min(axes)) / 2
            support = sum(values[a["id"]] for a in subset)
            ids = tuple(a["id"] for a in subset)
            if support > .5 and distance <= .55:
                candidates.append(((distance, count, -len(previous.intersection(ids)), -support, ids), ids))
    if candidates:
        ids = list(min(candidates)[1])
        return ids, [], "single_party_majority" if len(ids) == 1 else "majority_coalition", executive
    allies = [a for a in parties if a["id"] != winner and
              abs(a["economic_axis"] - next(b["economic_axis"] for b in parties if b["id"] == winner)) <= 1.30]
    support_ids = [a["id"] for a in allies]
    if values[winner] + sum(values[i] for i in support_ids) > .5:
        return [winner], support_ids, "supported_minority", executive
    return [winner], [], "caretaker", executive


def structural_inputs(p):
    """Formulas consume real mechanical inputs, never a regime score."""
    selected = [a for a in p["parties"] if a["id"] in p["government_ids"]]
    shares = [a["mandate_share"] for a in p["parties"]]
    cohesion = 0.0
    fragmentation = 0.0
    missing = 0.0
    if p["parliamentary_mandate"]:
        if len(selected) > 1:
            total = sum(a["mandate_share"] for a in selected)
            mean = sum(a["economic_axis"] * a["mandate_share"] for a in selected) / total
            cohesion = sum(abs(a["economic_axis"] - mean) * a["mandate_share"] for a in selected) / total
        fragmentation = max(0.0, min(1.0, (1 / math.fsum(s*s for s in shares) - 1) / 6))
        secured = sum(a["mandate_share"] for a in p["parties"] if a["id"] in p["government_ids"] + p["supporter_ids"])
        missing = max(0.0, min(1.0, (.5 - secured) / .5))
    return cohesion, fragmentation, missing


def political_target(base, cohesion, fragmentation, missing, pressure=0):
    return max(0.0, min(100.0, base - 10*cohesion - 6*fragmentation - 8*missing - pressure))


def candidate_premium(s_pol):
    """Release-gated candidate; no live bond/other consumer calls this."""
    return .0025 * max(0.0, min(1.0, (75 - s_pol) / 50))


def transition_pressure(p, when):
    transition = p["transition"]
    if transition is None:
        return 0.0
    start, end = date.fromisoformat(transition["start"]), date.fromisoformat(transition["end"])
    return transition["pressure"] * max(0.0, min(1.0, (end - when).days / max(1, (end - start).days)))


def refresh_components(p, when, macro, crisis=False, *, monthly=False):
    c, f, m = structural_inputs(p)
    target = political_target(p["base"], c, f, m)
    if monthly:
        p["structural_stability"] += .25 * (target - p["structural_stability"])
    p["political_stability"] = max(0.0, min(100.0, p["structural_stability"] - transition_pressure(p, when)))
    obs = macro_snapshot(macro)
    pressure = min(12.0, max(0, -obs["growth"])*80 + max(0, obs["unemployment"]-.08)*40 + max(0, obs["inflation"]-.04)*40)
    p["macro_pressure"] = min(18.0, pressure + (6 if crisis else 0))
    p["stability"] = max(0.0, min(100.0, p["political_stability"] - p["macro_pressure"]))
    p["premium"] = 0.0
    p["premium_revision"] = p["revision"]
    if p["transition"] and when >= date.fromisoformat(p["transition"]["end"]):
        p["transition"] = None


def create(seed, country, when, macro, *, heterogeneous=False, legacy=False, system=None):
    roots = rng(seed, country, "roots")
    system = system or (roots.choice(tuple(SYSTEMS)) if heterogeneous and not legacy else "parliamentary_democracy")
    _, cycle, competitive = SYSTEMS[system]
    count = (roots.randint(2, 7) if heterogeneous else 4) if competitive else (1 if system == "one_party_state" else 0)
    names = rng(seed, country, "names").sample([f"{w} {e}" for w in NAME_WORDS for e in NAME_ENDINGS], count)
    shares = normalize([roots.uniform(.2, 1) for _ in range(count)]) if heterogeneous and count else ([.4, .3, .2, .1] if competitive else [1.0]*count)
    parties = [{"id": f"{country}:p{i}", "name": names[i], "economic_axis": roots.uniform(-1, 1) if heterogeneous else (-.6, -.2, .2, .6)[i],
                "social_axis": roots.uniform(-1, 1) if heterogeneous else (-.4, .1, -.1, .4)[i],
                "initial_mandate_share": shares[i], "mandate_share": shares[i], "latest_vote_share": None}
               for i in range(count)]
    p = {"model_version": MODEL_VERSION, "calibration_version": CALIBRATION_VERSION, "system": system,
         "parliamentary_mandate": system in PARLIAMENTARY, "activated_on": when.isoformat(),
         "provenance": "legacy_activation" if legacy else "world_initialization", "parties": parties,
         "government_ids": [], "supporter_ids": [], "executive_id": None, "government_status": "continuity",
         "leadership_axes": [roots.uniform(-1, 1), roots.uniform(-1, 1)] if heterogeneous else [0.0, 0.0],
         "base": roots.uniform(70, 85) if heterogeneous else 75.0, "structural_stability": 75.0,
         "political_stability": 75.0, "stability": 75.0, "macro_pressure": 0.0, "transition": None,
         "next_election": None, "next_review": None, "last_election": None, "last_review": None,
         "sequence": 0, "event_sequence": 0, "revision": 0, "formation_date": when.isoformat(),
         "last_monthly": None, "published_macro": macro_snapshot(macro), "published_macro_source": "initialization", "election_baseline": macro_snapshot(macro),
         "latest_result": None, "recent_events": [], "premium": 0.0, "premium_revision": 0, "premium_enabled": False}
    p["government_ids"], p["supporter_ids"], p["government_status"], p["executive_id"] = form_government(p)
    c, f, m = structural_inputs(p)
    if not heterogeneous:
        p["base"] = 75 + 10*c + 6*f + 8*m
    p["structural_stability"] = political_target(p["base"], c, f, m)
    if cycle:
        due = add_years(when, cycle)
        if heterogeneous and not legacy:
            due = when + timedelta(days=roots.randint(180, max(181, (due-when).days)))
        p["next_election" if competitive else "next_review"] = due.isoformat()
    refresh_components(p, when, macro)
    return p


def event(state, country, p, when, kind, metadata, add_news=None):
    p["event_sequence"] += 1
    token = f"{MODEL_VERSION}|{getattr(state, 'simulation_seed', 0)}|{country}|{p['event_sequence']}|{kind}|{when}".encode()
    item = {"id": hashlib.sha256(token).hexdigest()[:24], "date": when.isoformat(), "type": kind, "metadata": deepcopy(metadata)}
    p["recent_events"] = (p["recent_events"] + [item])[-32:]
    out = getattr(state, "_politics_events", [])
    out.append((when.isoformat(), item["id"], country, kind, json_text(metadata)))
    state._politics_events = out
    if add_news:
        add_news(f" POLITICS: {country}: {kind.replace('_', ' ')}.", "WEISS")
    return item


def json_text(value):
    import json
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def rebuild_calendar(state):
    due = [p[key] for m in state.makro.values() if (p := m.get("politics")) for key in ("next_election", "next_review") if p[key]]
    state.politics_calendar = {"next_due": min(due) if due else None}


def initialize(state, *, seed=0, heterogeneous=False, legacy=False):
    changed = False
    when = day(state.datum)
    for country, macro in state.makro.items():
        if "politics" in macro:
            validate(macro["politics"], as_of=when, country=country)
            continue
        p = create(seed, country, when, macro, heterogeneous=heterogeneous, legacy=legacy)
        if country in (getattr(state, "aktives_event", None) or {}).get("laender", []):
            refresh_components(p, when, macro, crisis=True)
        macro["politics"] = p
        event(state, country, p, when, "politics_activation", {"provenance": p["provenance"]})
        changed = True
    rebuild_calendar(state)
    state._politics_dirty = True
    return changed


def election(state, country, p, when, add_news=None):
    """One immutable result, previous published inputs and isolated party streams."""
    p["sequence"] += 1
    old = p["published_macro"]
    base = p["election_baseline"]
    swing = max(-.04, min(.04, (old["growth"]-base["growth"])*.5 - (old["unemployment"]-base["unemployment"])*.4 - (old["inflation"]-base["inflation"])*.3 + (p["political_stability"]-75)*.0002))
    previous_ids = list(p["government_ids"])
    government_total = sum(a["mandate_share"] for a in p["parties"] if a["id"] in previous_ids)
    opposition_total = 1 - government_total
    values = []
    ordered = sorted(p["parties"], key=lambda a: a["id"])
    for a in ordered:
        share = a["mandate_share"]
        shift = swing * share / government_total if a["id"] in previous_ids else (-swing * share / opposition_total if opposition_total > 0 else 0)
        noise = rng(getattr(state, "simulation_seed", 0), country, f"election:{p['sequence']}:{a['id']}").uniform(-.01, .01)
        values.append(max(.001, share + shift + noise))
    shares = normalize(values)
    for a, share in zip(ordered, shares, strict=True):
        a["mandate_share"] = a["latest_vote_share"] = share
    p["government_ids"], p["supporter_ids"], p["government_status"], p["executive_id"] = form_government(p)
    changed = set(previous_ids) != set(p["government_ids"])
    pressure = 6.0 if p["government_status"] == "caretaker" else (3.0 if changed else 0.0)
    p["transition"] = {"start": when.isoformat(), "end": (when+timedelta(days=92)).isoformat(), "pressure": pressure} if pressure else None
    p["formation_date"] = p["last_election"] = when.isoformat()
    p["next_election"] = add_years(when, SYSTEMS[p["system"]][1]).isoformat()
    result = {"sequence": p["sequence"], "election_type": "executive_plurality" if p["system"] == "presidential_democracy" else "parliamentary_mandate",
              "shares": {a["id"]: a["latest_vote_share"] for a in ordered},
              "inputs": {"published_macro": deepcopy(old), "baseline_macro": deepcopy(base), "political_stability": p["political_stability"], "government_swing": swing,
                         "macro_available_on": p["last_monthly"] or p["activated_on"],
                         "macro_source": p.get("published_macro_source", "initialization")}}
    item = event(state, country, p, when, "election_result", result, add_news)
    p["latest_result"] = {**deepcopy(result), "id": item["id"], "date": when.isoformat()}
    status = p["government_status"]
    event(state, country, p, when, "formation_pending" if status == "caretaker" else ("minority_government" if status == "supported_minority" else ("government_formed" if changed else "incumbent_confirmed")),
          {"government_ids": p["government_ids"], "supporter_ids": p["supporter_ids"], "executive_id": p["executive_id"], "status": status}, add_news)
    p["election_baseline"] = deepcopy(old)


def process_due(state, when=None, add_news=None):
    when = day(when or state.datum)
    earliest = getattr(state, "politics_calendar", {}).get("next_due")
    if not earliest or when.isoformat() < earliest:
        return
    for country, macro in sorted(state.makro.items()):
        p = macro.get("politics")
        if not p:
            continue
        key = "next_election" if SYSTEMS[p["system"]][2] else "next_review"
        while p[key] and date.fromisoformat(p[key]) <= when:
            due = date.fromisoformat(p[key])
            if key == "next_election":
                election(state, country, p, due, add_news)
            else:
                p["sequence"] += 1
                p["last_review"] = due.isoformat()
                p[key] = add_years(due, 5).isoformat()
                event(state, country, p, due, "leadership_review", {"continuity": True}, add_news)
            p["revision"] += 1
            crisis = country in (getattr(state, "aktives_event", None) or {}).get("laender", [])
            refresh_components(p, due, macro, crisis)
            state._politics_dirty = True
    rebuild_calendar(state)


def refresh_crisis_pressure(state, previous):
    """Patch display pressure only when an economic crisis starts/ends."""
    active = getattr(state, "aktives_event", None)
    if previous is active:
        return
    old_countries = set((previous or {}).get("laender", []))
    new_countries = set((active or {}).get("laender", []))
    when = day(state.datum)
    for country in sorted(old_countries | new_countries):
        macro = state.makro.get(country, {})
        p = macro.get("politics")
        if not p:
            continue
        p["revision"] += 1
        refresh_components(p, when, macro, country in new_countries)
        event(state, country, p, when, "macro_pressure_changed",
              {"crisis_active": country in new_countries, "macro_pressure": p["macro_pressure"]})
        state._politics_dirty = True


def monthly(state, when=None, *, source="production_monthly_report"):
    when = day(when or state.datum)
    if when.day != 15:
        return
    for country, macro in sorted(state.makro.items()):
        p = macro.get("politics")
        if not p or (p["last_monthly"] and p["last_monthly"][:7] >= when.isoformat()[:7]):
            continue
        p["last_monthly"] = when.isoformat()
        p["revision"] += 1
        crisis = country in (getattr(state, "aktives_event", None) or {}).get("laender", [])
        refresh_components(p, when, macro, crisis, monthly=True)
        p["published_macro"] = macro_snapshot(macro)
        p["published_macro_source"] = source
        rows = getattr(state, "_politics_months", [])
        rows.append((when.isoformat(), country, p["political_stability"], p["macro_pressure"], p["stability"], p["premium"], p["revision"]))
        state._politics_months = rows
    state._politics_dirty = True


def advance_coarse(state, start, end, before):
    """All crossed reports and terms; economic hook is off, so no price replay."""
    dates = set()
    cursor = start.replace(day=15)
    if cursor <= start:
        cursor = (start.replace(day=28)+timedelta(days=4)).replace(day=15)
    while cursor <= end:
        dates.add(cursor)
        cursor = (cursor.replace(day=28)+timedelta(days=4)).replace(day=15)
    for macro in state.makro.values():
        p = macro.get("politics")
        if not p:
            continue
        for key in ("next_election", "next_review"):
            if p[key]:
                due = date.fromisoformat(p[key])
                while due <= end:
                    if due > start:
                        dates.add(due)
                    due = add_years(due, SYSTEMS[p["system"]][1])
    after = {c: macro_snapshot(m) for c, m in state.makro.items()}
    original = {c: {field: m[field] for field in ("bip_prozent", "arbeitslosigkeit", "inflation")} for c, m in state.makro.items()}
    try:
        for when in sorted(dates):
            fraction = (when-start).days / max(1, (end-start).days)
            for c, m in state.makro.items():
                for key, field in (("growth", "bip_prozent"), ("unemployment", "arbeitslosigkeit"), ("inflation", "inflation")):
                    m[field] = before[c][key] + fraction*(after[c][key]-before[c][key])
            process_due(state, when)
            if when.day == 15:
                monthly(state, when, source="coarse_interpolated_monthly_report")
    finally:
        for c, m in state.makro.items():
            m.update(original[c])


def projection(p):
    if not p:
        return {}
    selected = [a for a in p["parties"] if a["id"] in p["government_ids"]]
    if selected:
        total = sum(a["mandate_share"] for a in selected)
        axes = [sum(a[key]*a["mandate_share"] for a in selected)/total for key in ("economic_axis", "social_axis")]
    else:
        axes = p["leadership_axes"]
    return {"system": SYSTEMS[p["system"]][0], "system_code": p["system"], "stability": p["stability"],
            "political_stability": p["political_stability"], "macro_pressure": p["macro_pressure"],
            "status": p["government_status"], "government_ids": list(p["government_ids"]),
            "executive_id": p["executive_id"], "ideology": axes, "next_election": p["next_election"], "next_review": p["next_review"],
            "activated_on": p["activated_on"], "provenance": p["provenance"], "revision": p["revision"],
            "result_date": p["last_election"], "result_type": p["latest_result"]["election_type"] if p["latest_result"] else None,
            "parties": [{k: a[k] for k in ("id", "name", "mandate_share", "latest_vote_share")} for a in p["parties"]]}


def validate(p, *, as_of=None, country=None):
    """Reject malformed feature payload before load can mutate any live book."""
    try:
        if not isinstance(p, dict) or any(not isinstance(p[key], list) for key in ("parties", "government_ids", "supporter_ids", "recent_events")):
            raise ValueError("Invalid politics field types")
        if p["transition"] is not None and not isinstance(p["transition"], dict):
            raise ValueError("Invalid transition type")
        if p["model_version"] != MODEL_VERSION or p["calibration_version"] != CALIBRATION_VERSION or p["system"] not in SYSTEMS:
            raise ValueError("Unsupported politics model")
        _, _, competitive = SYSTEMS[p["system"]]
        parties = p["parties"]
        ids = [a["id"] for a in parties]
        count = len(ids)
        if len(set(ids)) != count or (competitive and not 2 <= count <= 7) or (not competitive and count != (1 if p["system"] == "one_party_state" else 0)):
            raise ValueError("Invalid political parties")
        if len({a["name"] for a in parties}) != count:
            raise ValueError("Duplicate party names")
        if any(not isinstance(i, str) or ":p" not in i or not i.rsplit(":p", 1)[0] for i in ids) or {i.rsplit(":p", 1)[1] for i in ids} != {str(i) for i in range(count)}:
            raise ValueError("Invalid stable party IDs")
        namespaces = {i.rsplit(":p", 1)[0] for i in ids}
        if len(namespaces) > 1 or (country is not None and namespaces and namespaces != {country}):
            raise ValueError("Invalid party country namespace")
        for group in (p["government_ids"], p["supporter_ids"]):
            if len(group) != len(set(group)) or not set(group) <= set(ids):
                raise ValueError("Invalid government references")
        if set(p["government_ids"]) & set(p["supporter_ids"]) or (p["executive_id"] is not None and p["executive_id"] not in ids):
            raise ValueError("Invalid executive/support references")
        if type(p["parliamentary_mandate"]) is not bool or p["parliamentary_mandate"] != (p["system"] in PARLIAMENTARY):
            raise ValueError("Invalid political mechanics")
        if p["premium_enabled"] is not False or p["premium"] != 0:
            raise ValueError("Political bond hook has not passed release gate")
        for key in ("base", "structural_stability", "political_stability", "stability", "macro_pressure"):
            v = p[key]
            if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 100:
                raise ValueError("Invalid political stability")
        for key in ("sequence", "event_sequence", "revision", "premium_revision"):
            if type(p[key]) is not int or p[key] < 0:
                raise ValueError("Invalid political sequence")
        activated = date.fromisoformat(p["activated_on"])
        if as_of is not None and (activated > day(as_of) or any(
            p[key] and date.fromisoformat(p[key]) > day(as_of)
            for key in ("formation_date", "last_election", "last_review", "last_monthly")
        )):
            raise ValueError("Future political history")
        if as_of is not None and any(p[key] and date.fromisoformat(p[key]) < day(as_of)
                                    for key in ("next_election", "next_review")):
            raise ValueError("Overdue saved political calendar")
        if p["provenance"] not in {"world_initialization", "legacy_activation"}:
            raise ValueError("Invalid politics provenance")
        for key in ("formation_date", "next_election", "next_review", "last_election", "last_review", "last_monthly"):
            if p[key] is not None and date.fromisoformat(p[key]) < activated:
                raise ValueError("Backdated politics")
        if competitive != (p["next_election"] is not None) or (competitive and p["next_review"] is not None):
            raise ValueError("Invalid election calendar")
        if p["system"] == "absolute_monarchy" and p["next_review"] is not None:
            raise ValueError("Invalid monarchy countdown")
        if p["system"] in {"one_party_state", "authoritarian_republic"} and p["next_review"] is None:
            raise ValueError("Missing leadership review")
        for key, last in (("next_election", "last_election"), ("next_review", "last_review")):
            if p[key] is not None and (date.fromisoformat(p[key]) <= activated or (p[last] and p[key] <= p[last])):
                raise ValueError("Invalid political term dates")
        if p["government_status"] not in {"continuity", "one_party_government", "plurality_executive", "single_party_majority", "majority_coalition", "supported_minority", "caretaker"}:
            raise ValueError("Invalid government status")
        if len(p["leadership_axes"]) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or not -1 <= v <= 1 for v in p["leadership_axes"]):
            raise ValueError("Invalid leadership ideology")
        for snapshot in (p["published_macro"], p["election_baseline"]):
            if set(snapshot) != {"growth", "unemployment", "inflation"} or any(type(v) not in (int, float) or not math.isfinite(v) for v in snapshot.values()):
                raise ValueError("Invalid political macro provenance")
        for a in parties:
            if not isinstance(a["id"], str) or not a["id"] or not isinstance(a["name"], str) or not a["name"]:
                raise ValueError("Invalid party identity")
            for key in ("economic_axis", "social_axis"):
                if type(a[key]) not in (int, float) or not math.isfinite(a[key]) or not -1 <= a[key] <= 1:
                    raise ValueError("Invalid ideology")
            for key in ("initial_mandate_share", "mandate_share"):
                if type(a[key]) not in (int, float) or not math.isfinite(a[key]) or not 0 < a[key] <= 1:
                    raise ValueError("Invalid mandate")
            vote = a["latest_vote_share"]
            if vote is not None and (not competitive or type(vote) not in (int, float) or not math.isfinite(vote) or not 0 < vote <= 1):
                raise ValueError("Invalid election share")
        for key in ("mandate_share", "initial_mandate_share"):
            if parties and not math.isclose(sum(a[key] for a in parties), 1, rel_tol=0, abs_tol=1e-14):
                raise ValueError("Political shares do not sum to one")
        if p["latest_result"] is not None:
            result = p["latest_result"]
            if not competitive or result["date"] != p["last_election"] or set(result["shares"]) != set(ids):
                raise ValueError("Invalid election result")
            result_date = date.fromisoformat(result["date"])
            available = date.fromisoformat(result["inputs"]["macro_available_on"])
            if not activated <= available <= result_date or result["sequence"] != p["sequence"] or p["sequence"] < 1:
                raise ValueError("Invalid election provenance")
            if not isinstance(result["id"], str) or len(result["id"]) != 24:
                raise ValueError("Invalid election identity")
            if any(result["shares"][a["id"]] != a["latest_vote_share"] or a["mandate_share"] != a["latest_vote_share"] for a in parties):
                raise ValueError("Election result changed")
            if not math.isclose(sum(result["shares"].values()), 1, rel_tol=0, abs_tol=1e-14):
                raise ValueError("Invalid result normalization")
        elif p["last_election"] is not None or any(a["latest_vote_share"] is not None for a in parties):
            raise ValueError("Fake past election")
        if p["transition"]:
            tr = p["transition"]
            if tr["start"] != p["formation_date"] or date.fromisoformat(tr["start"]) < activated or date.fromisoformat(tr["end"]) <= date.fromisoformat(tr["start"]) or type(tr["pressure"]) not in (int, float) or not math.isfinite(tr["pressure"]) or not 0 <= tr["pressure"] <= 8:
                raise ValueError("Invalid political transition")
        if len(p["recent_events"]) > 32 or len({e["id"] for e in p["recent_events"]}) != len(p["recent_events"]):
            raise ValueError("Invalid event identities")
        for item in p["recent_events"]:
            if date.fromisoformat(item["date"]) < activated or not isinstance(item["id"], str) or len(item["id"]) != 24 or not isinstance(item["metadata"], dict):
                raise ValueError("Invalid political event")
            if as_of is not None and date.fromisoformat(item["date"]) > day(as_of):
                raise ValueError("Future political event")
        # Also reject nonfinite values in nested immutable inputs/events.
        json_text(p)
    except (KeyError, TypeError, OverflowError) as error:
        raise ValueError("Malformed politics payload") from error
