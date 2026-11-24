# The flow map page

The last step of any build, and something a merchant can ask for on its own ("map my flows"). One page that shows every flow in the account, where Antla enters each one, and what to fix first. It is the hand-over a merchant actually reads, so build it from what you read back from Klaviyo, never from what you meant to build.

## What goes on the page, in this order

1. **Fix first.** Problems ordered by how likely each one is to send a shopper the wrong email, or none. Each has a severity (`crit`, `warn`, `info`), a one-line headline and one or two plain sentences that name the flows and the fix. Look for:
   - two or more **live** flows on one trigger (double sends), counting the merchant's own and test flows;
   - a webhook pointing at a campaign whose real events show a different product than the flow promises;
   - a flow that went live without the user asking, or a live flow on a trigger that has stopped firing;
   - a campaign whose output is unknown (sample event only), and any field path that could not be confirmed on a real event.
2. **Are the triggers firing?** Last event date for each trigger the map uses (`ok` recent, `warn` weeks old, `crit` never).
3. **The try-on map.** One diagram per Antla flow: every path from trigger to an end, drawn as a left-to-right tree.
4. **Antla campaigns.** Name, token (first 8 characters + "…"), its Klaviyo flow and status, what it generates (only from real events), which flows use it.
5. **Every flow, by trigger.** Every flow in the account grouped by trigger metric, with status and role (`Try-on map`, `Antla campaign`, `Store flow`, `Older Antla build`, `Test`).

Gathering it: `get_flows` (all, with status; 50 a page, so follow `page_cursor` until there is no next page); `get_metrics` with `include: ["flow-triggers"]` gives trigger → flows in one call (large: request `fields_metric: ["name","integration.name"]`); `get_flow` with the definition for each Antla flow; one `get_events` per trigger for the last event; the campaign inventory from SKILL.md step 1b.

## The spec file

`scripts/build_flow_map.py spec.json out.html` turns a JSON spec into the page, using `assets/flow-map-template.html` (Antla's grid style, light and dark). The output is a page body for publishing as an artifact, where the host supplies the document head. When the merchant will open the file from disk or receive it as an attachment, add `--standalone` to get a complete HTML document. Where you cannot run code, write the same page by hand from the template: the sections, tags and colours are all in it.

```json
{"store": "Store name", "date": "24 Nov 2026",
 "attention": [["crit", "Headline", "One or two sentences naming flows and the fix."]],
 "triggers": [["Added to Cart", "Nov 19", "ok"]],
 "flows": [{"id": "FLOWID", "name": "Abandoned cart", "status": "draft", "note": "One line of context.",
   "tree": {"kind": "trigger", "title": "Added to Cart", "sub": "no order · once a day", "kids": [
     ["", {"kind": "delay", "title": "Wait 1 hour", "kids": [
       ["", {"kind": "split", "title": "Photo on file?", "sub": "antla_user_image_url", "kids": [
         ["yes", {"kind": "webhook", "title": "Webhook to Antla", "sub": "Campaign name", "kids": [
           ["", {"kind": "delay", "title": "Wait 30 min", "kids": [
             ["", {"kind": "split", "title": "Look arrived?", "sub": "campaign event", "kids": [
               ["yes", {"kind": "look", "title": "Antla sends the look", "sub": "campaign flow"}],
               ["no",  {"kind": "email", "title": "Cart reminder", "sub": "fallback"}]]}]]}]]}],
         ["no",  {"kind": "email", "title": "Cart reminder", "sub": "+ See it on you"}]]}]]}]]}}],
 "campaigns": [["Campaign", "a1b2c3d4…", "FLOWID", "live", ["Recommendation", "ok"], "Post-purchase, win-back"]],
 "all": [["Added to Cart", [["FLOWID", "Flow name", "live", "Store flow"]]]]}
```

Node `kind`s: `trigger`, `delay` (folded into the next box as "AFTER …"), `split`, `webhook`, `email` (a store email), `tryon` (an email that shows the shopper's try-on), `look` (the end where the Antla campaign's own flow sends the look). Optional `tone`: `warn` (wrong product or a known problem) or `unk` (untested). Edge labels are `"yes"`/`"no"` on splits and `""` elsewhere. Each entry in `kids` is a pair, `[edge label, node]`. Statuses are `live`, `draft`, `manual`, or `none` for a campaign with no flow. A path that stops on a `delay`, or a `kind` not in this list, is drawn as a problem box rather than left out. Keep titles to about 22 characters and subs to about 26 so they fit the boxes.

## Rules

- Draw the read-back, not the plan: build each tree from `get_flow`, and mark anything you could not verify (`tone: "unk"`) instead of drawing it as working.
- Every path must end in an email or a `look`. A path that ends anywhere else is itself an item for "Fix first".
- No personal data: no shopper emails, no profile IDs. Flow and campaign names and flow IDs are fine; the merchant owns them. Tokens are shortened to the first 8 characters, and no webhook URL appears anywhere on the page: the page gets shared, and the token is the webhook's only authentication.
- Publish it as a page the merchant can open (an artifact where the client supports one; otherwise the HTML file) and give them the link.
