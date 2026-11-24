#!/usr/bin/env python3
"""Check a Klaviyo flow as it was READ BACK from Klaviyo (not as it was sent).

Usage:
    python3 verify_flow.py flow.json [--expect-actions N] [--expect-links N]
    python3 verify_flow.py - < flow.json

flow.json is the result of the Klaviyo MCP `get_flow` call made with
additional_fields_flow=["definition"]. Any of these shapes is accepted:
the whole tool result, its "data" object, the "attributes" object, or the
bare definition.

It prints every path a shopper can take, then a list of problems.
Exit code is 1 when there is at least one ERROR, otherwise 0.

Why this exists: Klaviyo accepts a flow definition and can silently drop
links it does not support (for example, branches of different splits joining
the same later step). The create call succeeds and the flow looks fine in a
summary, but some paths now end early. Only a read-back shows it.

Works on Python 3.8+ with the standard library only.
"""
import json
import re
import sys

ANTLA_WEBHOOK = re.compile(r"^https://app-antla\.com/integrations/klaviyo/webhook/[0-9a-f]{16}$")
PLACEHOLDER_HINTS = ("customer@example.com", "123456789", "example.com/customer-photo", "Email #1 Subject")


def find_definition(obj):
    """Dig through the usual wrappers until we find the object holding 'actions'."""
    seen = 0
    while isinstance(obj, dict) and "actions" not in obj and seen < 6:
        seen += 1
        for key in ("result", "data", "attributes", "definition"):
            if key in obj and isinstance(obj[key], dict):
                obj = obj[key]
                break
        else:
            break
    return obj if isinstance(obj, dict) and "actions" in obj else None


def flow_meta(raw):
    obj = raw
    for key in ("result", "data"):
        if isinstance(obj, dict) and key in obj and isinstance(obj[key], dict):
            obj = obj[key]
    attrs = obj.get("attributes", {}) if isinstance(obj, dict) else {}
    return attrs.get("name"), attrs.get("status")


def out_links(action):
    """Return [(label, target_id_or_None)] for an action."""
    t = action.get("type")
    links = action.get("links") or {}
    if t in ("conditional-split", "trigger-split", "action-output-split"):
        return [("YES", links.get("next_if_true")), ("NO", links.get("next_if_false"))]
    if t == "multi-branch-split":
        res = []
        for b in (action.get("data") or {}).get("branches", []):
            label = b.get("name") or ("ELSE" if b.get("is_else") else b.get("branch_id", "branch"))
            if b.get("is_else") and not b.get("name"):
                label = "ELSE"
            res.append((label, (b.get("links") or {}).get("next")))
        return res
    return [("", links.get("next"))]


def describe(action):
    t = action.get("type")
    d = action.get("data") or {}
    m = d.get("message") or {}
    if t == "time-delay":
        return "wait %s %s" % (d.get("value"), d.get("unit"))
    if t == "send-email":
        return "EMAIL \"%s\" (subject: %s)" % (m.get("name"), m.get("subject_line"))
    if t == "send-sms":
        return "SMS \"%s\"" % m.get("name")
    if t == "send-webhook":
        return "WEBHOOK \"%s\"" % m.get("name")
    if t == "update-profile":
        keys = [op.get("property_key") for op in d.get("profile_operations", [])]
        return "set profile %s" % ", ".join(str(k) for k in keys)
    if t == "multi-branch-split":
        return "split \"%s\"" % d.get("name")
    if t in ("conditional-split", "trigger-split"):
        return "%s?" % t
    return str(t)


def check_webhook(action, errors, warnings):
    m = (action.get("data") or {}).get("message") or {}
    name = m.get("name")
    url = m.get("url") or ""
    body = m.get("body") or ""
    if "app-antla.com" in url and not ANTLA_WEBHOOK.match(url):
        errors.append("Webhook \"%s\": URL is not a well-formed Antla webhook (expected .../webhook/<16 hex characters>): %s" % (name, url))
    if "app-antla.com" not in url:
        return
    if not body.strip():
        errors.append("Webhook \"%s\": body is empty." % name)
        return
    # Replace template tags so the body can be parsed as JSON.
    probe = re.sub(r"\{\{.*?\}\}", "x", body)
    probe = re.sub(r"\{%.*?%\}", "", probe)
    try:
        parsed = json.loads(probe)
    except ValueError:
        errors.append("Webhook \"%s\": body is not valid JSON once template tags are filled in." % name)
        return
    if not isinstance(parsed, dict):
        errors.append("Webhook \"%s\": body must be a JSON object." % name)
        return
    if "email" not in parsed:
        errors.append("Webhook \"%s\": body has no \"email\" key." % name)
    if "productId" not in parsed:
        hint = " It has \"product_id\"; Antla rejects that with a 400." if "product_id" in parsed else ""
        errors.append("Webhook \"%s\": body has no \"productId\" key (exact camelCase).%s" % (name, hint))
    for key in ("email", "productId"):
        raw = re.search(r'"%s"\s*:\s*("[^"]*"|[^,}\s]+)' % key, body)
        if raw and "{{" not in raw.group(1):
            errors.append("Webhook \"%s\": \"%s\" is a fixed value (%s), not a template variable. Every shopper would send the same value." % (name, key, raw.group(1)))
    for hint in PLACEHOLDER_HINTS:
        if hint in body:
            errors.append("Webhook \"%s\": body still contains example text (%s)." % (name, hint))


def check_email(action, errors, warnings):
    m = (action.get("data") or {}).get("message") or {}
    name = m.get("name")
    if not m.get("template_id"):
        errors.append("Email \"%s\": no template attached." % name)
    subject = (m.get("subject_line") or "").strip()
    if not subject:
        errors.append("Email \"%s\": subject line is empty." % name)
    for hint in PLACEHOLDER_HINTS:
        if hint in subject:
            errors.append("Email \"%s\": subject is still the default placeholder." % name)
    if not m.get("from_email"):
        warnings.append("Email \"%s\": no sender address set." % name)
    if not (m.get("preview_text") or "").strip():
        warnings.append("Email \"%s\": no preview text." % name)


def main(argv):
    args = [a for a in argv[1:]]
    expect_actions = expect_links = None
    path = None
    i = 0
    while i < len(args):
        if args[i] == "--expect-actions":
            expect_actions = int(args[i + 1]); i += 2
        elif args[i] == "--expect-links":
            expect_links = int(args[i + 1]); i += 2
        else:
            path = args[i]; i += 1
    if path is None:
        print(__doc__)
        return 2
    text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    raw = json.loads(text)
    definition = find_definition(raw)
    if definition is None:
        print("ERROR: could not find a flow definition with 'actions' in the input. "
              "Call get_flow with additional_fields_flow=[\"definition\"].")
        return 1

    name, status = flow_meta(raw)
    actions = definition.get("actions") or []
    by_id = {str(a.get("id") or a.get("temporary_id")): a for a in actions}
    entry = definition.get("entry_action_id")
    errors, warnings, notes = [], [], []
    if any(a.get("temporary_id") and not a.get("id") for a in actions):
        errors.append("This looks like the definition you SENT (it has temporary_id values). Verify the read-back from get_flow instead.")

    # ---- counts ---------------------------------------------------------
    link_count = 0
    for a in actions:
        for label, target in out_links(a):
            if target is not None:
                link_count += 1
                if str(target) not in by_id:
                    errors.append("%s links to %s, which is not an action in this flow." % (describe(a), target))
    print("Flow: %s   status: %s" % (name or "(name not in input)", status or "(status not in input)"))
    print("Actions: %d   Links (non-empty): %d" % (len(actions), link_count))
    if expect_actions is not None and expect_actions != len(actions):
        errors.append("Expected %d actions but Klaviyo has %d." % (expect_actions, len(actions)))
    if expect_links is not None and expect_links != link_count:
        errors.append("Expected %d links but Klaviyo has %d. Klaviyo dropped or changed %d link(s): compare the paths below with what you intended."
                      % (expect_links, link_count, abs(expect_links - link_count)))

    # ---- entry & reachability -------------------------------------------
    if entry is None:
        warnings.append("entry_action_id is not in the input, so reachability was judged from links alone. Include definition.entry_action_id in the read-back.")
        targeted = {str(t) for a in actions for _, t in out_links(a) if t is not None}
        roots = [k for k in by_id if k not in targeted]
        entry = roots[0] if roots else (next(iter(by_id)) if by_id else None)
        if len(roots) > 1:
            errors.append("%d actions have nothing leading to them (%s). One is the entry; the others are unreachable." % (len(roots), ", ".join(roots)))
    elif str(entry) not in by_id:
        errors.append("entry_action_id %s is not an action in this flow." % entry)

    # ---- walk every path ------------------------------------------------
    paths = []
    reached = set()

    def walk(aid, trail, seen):
        aid = str(aid)
        if aid in seen:
            errors.append("Loop inside the flow at action %s." % aid)
            return
        a = by_id.get(aid)
        if a is None:
            return
        reached.add(aid)
        for label, target in out_links(a):
            step = (a, label)
            if target is None:
                paths.append(trail + [step])
            else:
                walk(target, trail + [step], seen | {aid})

    if entry is not None:
        walk(entry, [], set())

    unreachable = [k for k in by_id if k not in reached]
    for k in unreachable:
        errors.append("Unreachable action: %s (id %s). Nothing in the flow leads to it." % (describe(by_id[k]), k))

    print("\nPaths a shopper can take (%d):" % len(paths))
    for n, p in enumerate(paths, 1):
        parts = []
        for a, label in p:
            parts.append(describe(a) + (" [%s]" % label if label else ""))
        print("  %d. %s -> END" % (n, "  ->  ".join(parts)))

    # ---- per-path checks ------------------------------------------------
    for n, p in enumerate(paths, 1):
        types = [a.get("type") for a, _ in p]
        messaging = [a for a, _ in p if a.get("type") in ("send-email", "send-sms", "send-webhook", "send-whatsapp", "send-mobile-push")]
        last_action, last_label = p[-1]
        if not messaging:
            notes.append("Path %d sends nothing (no email, SMS or webhook). Confirm that is intended, e.g. an exit for shoppers who already converted." % n)
        if last_action.get("type") == "send-webhook":
            warnings.append("Path %d ends at a webhook with nothing after it. Antla silently drops requests it cannot fulfil, so add a wait, a check for the campaign event, and a fallback email." % n)
        if last_action.get("type") in ("multi-branch-split",):
            errors.append("Path %d: branch \"%s\" of %s leads nowhere." % (n, last_label, describe(last_action)))
        if last_action.get("type") == "time-delay":
            errors.append("Path %d ends on a delay with nothing after it." % n)
        subjects = [((a.get("data") or {}).get("message") or {}).get("subject_line") for a, _ in p if a.get("type") == "send-email"]
        dupes = {s for s in subjects if s and subjects.count(s) > 1}
        for s in dupes:
            warnings.append("Path %d sends two emails with the same subject (\"%s\"). Make the follow-up different." % (n, s))

    for a in actions:
        t = a.get("type")
        if t in ("conditional-split", "trigger-split"):
            links = out_links(a)
            if all(target is None for _, target in links):
                errors.append("%s (id %s): both branches lead nowhere." % (describe(a), a.get("id")))
        if t == "send-email":
            check_email(a, errors, warnings)
        if t == "send-webhook":
            check_webhook(a, errors, warnings)

    # ---- statuses -------------------------------------------------------
    statuses = {}
    for a in actions:
        s = (a.get("data") or {}).get("status")
        if s:
            statuses.setdefault(s, []).append(describe(a))
    if statuses:
        print("\nAction statuses: " + ", ".join("%s x%d" % (s, len(v)) for s, v in sorted(statuses.items())))
    if status == "live":
        for s, items in statuses.items():
            if s != "live":
                for item in items:
                    warnings.append("Flow is live but this action is %s and will not run: %s" % (s, item))

    # ---- report ---------------------------------------------------------
    print("")
    for e in errors:
        print("ERROR   " + e)
    for w in warnings:
        print("WARNING " + w)
    for x in notes:
        print("NOTE    " + x)
    if not (errors or warnings or notes):
        print("No problems found.")
    print("\n%d error(s), %d warning(s), %d note(s)." % (len(errors), len(warnings), len(notes)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
