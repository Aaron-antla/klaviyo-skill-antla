"""Build the Antla flow map page for a merchant's Klaviyo account.

Usage: python3 build_flow_map.py spec.json out.html
spec.json is described in references/flow-map.md. The page template is assets/flow-map-template.html.
"""
import html, json, os, sys
E = html.escape
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- tree layout -> SVG (Antla homepage style) ----------
BW, BH, GAP, ROW, PADX, PADY = 200, 78, 56, 104, 2, 28
COL = BW + GAP
TAG = {"trigger": "TRIGGER", "split": "SPLIT", "webhook": "WEBHOOK", "email": "EMAIL",
       "tryon": "TRY-ON EMAIL", "look": "ANTLA SENDS"}

def fold_delays(node, branch="", after=""):
    """Waits become the next box's label; yes/no becomes the child's label."""
    while node["kind"] == "delay" and len(node["kids"]) == 1:
        t = node["title"]
        after = t[5:] if t.lower().startswith("wait ") else t
        node = node["kids"][0][1]
    node = dict(node)
    node["branch"], node["after"] = branch, after
    node["kids"] = [(lab, fold_delays(k, lab)) for lab, k in node["kids"]]
    return node

def layout(node, depth, rows):
    node["d"] = depth
    if not node["kids"]:
        node["r"] = rows[0]; rows[0] += 1
    else:
        for _, k in node["kids"]:
            layout(k, depth + 1, rows)
        ys = [k["r"] for _, k in node["kids"]]
        node["r"] = (min(ys) + max(ys)) / 2

def walk(node):
    yield node
    for _, k in node["kids"]:
        yield from walk(k)

def eyebrow(n):
    parts = []
    if n.get("branch"):
        parts.append(n["branch"].upper())
    parts.append(("AFTER " + n["after"].upper()) if n.get("after") else TAG[n["kind"]])
    return " \u00b7 ".join(parts)

def role(n):
    if n.get("tone") == "warn": return "warn"
    if n.get("tone") == "unk": return "unk"
    if n["kind"] in ("tryon", "look"): return "hit"
    if n["kind"] == "email": return "store"
    return "antla"

def svg_for(flow):
    t = fold_delays(flow["tree"]); rows = [0]
    layout(t, 0, rows)
    nodes = list(walk(t))
    maxd = max(n["d"] for n in nodes)
    W = PADX * 2 + maxd * COL + BW
    H = PADY * 2 + (rows[0] - 1) * ROW + BH
    pos = lambda n: (PADX + n["d"] * COL, PADY + n["r"] * ROW)
    out = [f'<svg viewBox="0 0 {W} {H}" width="{W}" role="img" aria-label="{E(flow["name"])}: every path a shopper can take, left to right">']
    for n in nodes:
        x, y = pos(n)
        for lab, k in n["kids"]:
            kx, ky = pos(k)
            x1, y1, x2, y2 = x + BW, y + BH / 2, kx, ky + BH / 2
            mx = x1 + GAP / 2
            out.append(f'<path class="edge e-{role(k)}" d="M{x1},{y1} H{mx} V{y2} H{x2}"/>')
    for n in nodes:
        x, y = pos(n)
        r = role(n)
        out.append(f'<g class="node k-{n["kind"]} r-{r}"><rect x="{x}" y="{y}" width="{BW}" height="{BH}"/>')
        out.append(f'<text class="eb" x="{x + 16}" y="{y + 22}">{E(eyebrow(n))}</text>')
        out.append(f'<text class="tt" x="{x + 16}" y="{y + 45}">{E(n["title"])}</text>')
        if n["sub"]:
            out.append(f'<text class="sb" x="{x + 16}" y="{y + 64}">{E(n["sub"])}</text>')
        out.append('</g>')
    out.append('</svg>')
    return "\n".join(out)

def pill(status):
    return f'<span class="pill p-{status}">{"Live" if status == "live" else ("Draft" if status == "draft" else "No flow")}</span>'

def flowlink(fid):
    if fid == "none":
        return '<span class="muted">none</span>'
    return f'<a class="mono" href="https://www.klaviyo.com/flow/{fid}/edit">{fid}</a>'

TONES = {"ok": "Known", "warn": "Check", "crit": "Problem", "unk": "Unknown", "info": "Note"}

TONES = {"ok": "Known", "warn": "Check", "crit": "Problem", "unk": "Unknown", "info": "Note"}

def main(spec_path, out_path):
    spec = json.load(open(spec_path))
    for f in spec["flows"]:
        def conv(n):
            return {"kind": n["kind"], "title": n["title"], "sub": n.get("sub", ""), "tone": n.get("tone", ""),
                    "kids": [(l, conv(k)) for l, k in n.get("kids", [])]}
        f["tree"] = conv(f["tree"])
    ALL = spec["all"]
    total = sum(len(fl) for _, fl in ALL)
    live = sum(1 for _, fl in ALL for f in fl if f[2] == "live")
    cards = [f'''<article class="flow" id="f-{f["id"]}">
  <header class="flow-h"><div><h3>{E(f["name"])}</h3><p class="note">{E(f.get("note", ""))}</p></div>
  <div class="flow-meta">{pill(f["status"])} {flowlink(f["id"])}</div></header>
  <figure><div class="scroll">{svg_for(f)}</div></figure>
</article>''' for f in spec["flows"]]
    att = "\n".join(f'<li class="att a-{t}"><span class="sev">{TONES[t]}</span><div><strong>{E(h)}</strong><p>{E(b)}</p></div></li>' for t, h, b in spec["attention"])
    trig = "\n".join(f'<li><span class="dot d-{h}"></span><span>{E(n)}</span><span class="mono muted">{E(d)}</span></li>' for n, d, h in spec["triggers"])
    camp = "\n".join(f'<tr><td>{E(n)}</td><td class="mono">{E(t)}</td><td>{flowlink(fl)} {pill(s) if s != "none" else ""}</td><td><span class="tag tg-{g[1]}">{E(g[0])}</span></td><td>{E(u)}</td></tr>' for n, t, fl, s, g, u in spec["campaigns"])
    rows = []
    for tname, fl in ALL:
        nl = sum(1 for f in fl if f[2] == "live")
        rows.append(f'<tr class="grp"><th colspan="4">{E(tname)} <span class="muted">· {len(fl)} flows, {nl} live</span></th></tr>')
        rows += [f'<tr><td>{E(nm)}</td><td>{flowlink(fid)}</td><td>{pill(st)}</td><td><span class="role">{E(role)}</span></td></tr>' for fid, nm, st, role in fl]
    page = open(os.path.join(HERE, "..", "assets", "flow-map-template.html")).read()
    vals = {"store": E(spec["store"]), "date": E(spec["date"]), "cards": "\n".join(cards), "att": att, "trig": trig,
            "camp": camp, "allrows": "\n".join(rows), "total": str(total), "live": str(live),
            "nmap": str(len(spec["flows"])), "ncamp": str(len(spec["campaigns"]))}
    for k, v in vals.items():
        page = page.replace("%%" + k + "%%", v)
    open(out_path, "w").write(page)
    print("wrote", out_path)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
