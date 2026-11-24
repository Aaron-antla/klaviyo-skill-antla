---
name: antla-klaviyo
description: Build Klaviyo flows, emails, segments and campaigns that use Antla AI virtual try-on data, through the Klaviyo MCP. Covers the try-on metric, Antla campaign events, Antla profile properties, the Antla campaign webhook (so abandoned cart, browse abandonment, post-purchase and win-back flows can end in an email showing the shopper wearing the product), ready-made email templates, tested create_flow recipes, and how to test and debug it all. Use this whenever someone with Antla and Klaviyo wants to set up, improve, personalise or troubleshoot email or SMS marketing, even if they only say "abandoned cart flow", "try-on email", "use the Antla webhook", "why didn't the try-on email send", "antla_looks", "Antla campaign event", or ask what they can do with virtual try-on in their emails.
---

# Antla + Klaviyo

Antla is a virtual try-on app for Shopify: a shopper uploads a photo and sees themselves wearing a product. Antla's Klaviyo integration sends that into Klaviyo, so emails can show each shopper **themselves** in the product instead of a catalog photo. This skill is how to build with it through the Klaviyo MCP.

Work from what is actually in the user's account. Metric IDs, template IDs, sender details and webhook URLs differ for every store, so discover them; nothing in this skill's files is an ID to reuse.

## What Antla puts in Klaviyo

There are three sources of data and one way to ask for more.

| | What it is | Use it for |
|---|---|---|
| **`Customer tried-on an outfit`** metric | Fires on every try-on. Carries the generated image, product, category and lifetime count. | Triggering flows on try-on behaviour; "has tried on recently" splits; segments. |
| **`Antla Campaign Event: <name> [<token>]`** metrics | One per flow created in the Antla app. Carries the content Antla prepared: the original try-on and/or up to 6 recommended looks generated on the shopper's photo, tracked links, an optional discount. | Triggering the email that shows the looks. These are the only events that carry `antla_looks`. |
| **Profile properties** (`antla_last_tryon_image_url`, `antla_tryon_count`, `antla_user_image_url`, …) | Kept current on each profile. | Personalising any email, including ordinary campaigns; splits; segments. |
| **Campaign webhook** (`https://app-antla.com/integrations/klaviyo/webhook/<token>`) | POST an email and a product ID, and Antla generates that campaign's content for that shopper and sends the campaign event. | Putting a personalised look at the end of a flow Antla doesn't trigger: abandoned checkout, browse abandonment, post-purchase, win-back. |

Full property lists, template variables and where each trigger keeps its product ID: `references/data-reference.md`.

The pattern that makes the webhook useful is a two-flow relay:

```
Flow A (Shopify trigger, e.g. Checkout Started) ── webhook ──▶ Antla campaign ── campaign event ──▶ Flow B (sends the email with the looks)
```

Flow A chooses who and when. The Antla campaign chooses what gets generated. Flow B is the email. A webhook is one-way, so Flow A can never display the generated image itself.

## How to work

### 1. Look before building

Run these first; they are cheap and they prevent most mistakes.

- `get_metrics` with `filter: equals(integration.name,"Antla")` and `fields_metric: ["name"]` lists the try-on metric and every campaign metric. No results means the integration isn't connected; send the user to Antla → Integrations → Klaviyo.
- `get_metrics` again without the filter (ask only for `name` and `integration.name`) to find the store's `Checkout Started`, `Placed Order`, `Added to Cart`, `Viewed Product` metric IDs. There can be two metrics with the same name from different integrations; use the one the store's existing flows use.
- `get_flows` with `fields_flow: ["id","name","status","trigger_type"]`. Read the definition (`get_flow` with `additional_fields_flow: ["definition"]`) of anything on the trigger you are about to use, and of any Antla-created flow you will rely on.
- `get_account_details` for the sender name, sender email and store URL.
- For every trigger you might build on, check it is firing: `get_events` filtered by its metric, `page_size: 1`, `sort: -datetime`. A metric whose last event is weeks old (an integration change can silently stop Checkout Started, for example) means a flow on it will never run. Tell the user and suggest the trigger that is live (Added to Cart instead of Checkout Started, say).

Responses can be large. Ask for the fields you need, and avoid pulling full template HTML or whole Shopify checkout events into the conversation.

### 1a. Build on the merchant's own flows

Every store already emails shoppers at the moments that matter. Antla's job is to add the shopper's own image to those emails, not to replace the store's marketing. So before designing anything, list the merchant's flows by purpose (abandoned checkout, abandoned cart, browse abandonment, post-purchase, win-back, back in stock, welcome) and read the definition of each one you will touch: trigger, flow filters, delays, how many emails, and each email's `template_id`, subject line and sender.

Then build the Antla version **from** that flow:
- Same trigger, same flow filters, same timing, same sender. The merchant has tuned these; keep them unless they ask otherwise.
- Reuse their email templates for every non-try-on email, including every fallback: put their `template_id` on the new email action (Klaviyo clones it into the flow, so their original is untouched). Their customers keep getting the store's own design and copy.
- Insert the Antla part where it fits: a split on Antla data before the first email, the webhook relay, or a try-on email in place of (or before) their first reminder.
- `create_flow` cannot edit an existing flow, so the result is a new draft flow. Name it after theirs ("<their flow name> + Antla try-on"), and in the hand-over say that their original must be set to draft when the new one goes live, or shoppers get both.

Use the templates in `assets/` only for the try-on emails themselves, and for any purpose the merchant has no flow for yet. When you do, take the store's name, logo and colours from the account (`get_brand_logos`, `get_brand_colors`, `get_account_details`), not the placeholders.

### 1b. Map the Antla campaigns before choosing a webhook

Each flow needs the campaign whose output fits it, so build a small inventory first and pick from it per flow; never reuse one campaign's webhook everywhere.

- Every `Antla Campaign Event: <name> [<token>]` metric is a campaign, and its webhook URL is `https://app-antla.com/integrations/klaviyo/webhook/<token>`. You can build it yourself; the merchant does not need to paste it.
- For each campaign note: its Klaviyo flow (`get_metrics` with `include: ["flow-triggers"]`) and whether that flow and its email are live (no live flow = no email ever sends), the email's subject line, and what it generates.
- What it generates comes only from **real** events (`antla_test_event` false). The sample event Antla sends on creation is identical for every campaign type, so it tells you nothing. Compare `antla_original_product` with `antla_looks[*].product_title`: same product (or `antla_original_tryon_image_url` set) = a "Their photo" campaign; different products = a recommendation campaign.
- A campaign with no real events is unknown. Ask the merchant what type it is, or, with their permission, send one webhook call with their own email and a known product and read the event that arrives (this sends them one real email).

Match campaigns to flows by what the email must show:

| Flow | Needs |
|---|---|
| Abandoned checkout / cart, browse abandonment, back in stock | The same product on the shopper ("Their photo"), with copy that fits that moment |
| Post-purchase, win-back, new arrivals | A recommendation ("1 recommendation" / "Multiple") |

If no campaign fits a flow, say which one to create in the Antla app (type, copy, a name that says its purpose, e.g. "Webhook · Their photo · Cart"), and build the rest meanwhile. Never point a flow at a campaign that shows a different product than the flow's email promises.

### 2. Agree what to build

If the user has a specific request, build that. If they ask what is possible, read `references/playbook.md` and propose the two or three plays that fit what their account already has. Say plainly which parts need the Antla app: only the merchant can create an Antla campaign, choose its email type and audience, set a discount, or write the campaign's email copy.

### 3. Design every path, then build in draft

Before writing any JSON, list every path a shopper can take from the trigger to an end and what they receive on each. A path that ends at a webhook, or only sets a profile property, has sent the shopper nothing. Every webhook path needs a wait, a check that the campaign event arrived, and a fallback email, because Antla drops requests silently.

If the user pasted a webhook URL, validate it first: its 16-character token must appear in the name of an Antla campaign metric in the account. No match means a bad paste; stop and ask again.

Then use the definitions in `references/flow-recipes.md`; they are written in the exact shape `create_flow` accepts and include the errors you are likely to hit. For try-on emails use the templates in `assets/` (replace the `__PLACEHOLDERS__`, then `create_email_template` with `editor_type: "CODE"`); for everything else use the merchant's own templates (step 1a). Where the account has brand assets (`get_brand_logos`, `get_brand_colors`), use them in the template instead of the plain text wordmark.

Keep the flow a tree: when several paths need the same later steps, give each path its own copy. Klaviyo has silently dropped links where separate branches converged on one shared step.

New flows and their actions are created in draft. Leave them there.

### 4. Run the verification pass

Read `references/verification.md` and do all of it. In short: read the flow back from Klaviyo and compare it with what you designed, path by path (`scripts/verify_flow.py` does this mechanically and catches dropped links, dead-end branches, unreachable actions, missing templates and malformed webhook bodies); render every template with full and with missing data; validate the webhook; and check for other live flows on the same trigger.

A create call that succeeded proves only that the request was well-formed. Do not describe a flow as built or ready until it has been read back and matches. This step is not optional and not shortened for "simple" flows; the mistakes it catches came from flows that looked simple.

### 5. Hand over, and go live only when told

Give the user the editor link (`https://www.klaviyo.com/flow/<FLOW_ID>/edit`) and the list of paths, and separate what was verified, what could not be verified from here, and what needs their decision. Turning a flow live sends real messages to real customers, so do it only when the user says to, and raise any flow that shares the trigger first. After any status change, read the status back.

### 6. Map every flow

Finish every build with the flow map: one page showing every flow in the account, where Antla enters each one, and what to fix first (double sends on one trigger, a webhook showing the wrong product, triggers that stopped firing, anything unverified). Read `references/flow-map.md`; `scripts/build_flow_map.py` builds the page from a JSON spec, and `assets/flow-map-template.html` is the page design. Merchants can also ask for the map on its own, to see where they stand before building anything.

## Rules that keep shoppers and the account safe

**The try-on must be visible.** A merchant judges an Antla flow from the Klaviyo canvas and the email preview. Every Antla flow needs an Antla step on the canvas (an Antla trigger, a split on Antla data, or a webhook to an Antla campaign), and its try-on email must show the try-on image as the hero without a condition hiding it. Klaviyo's preview has profile data but no event data, so an image that only renders when an event field matches (for example "cart item = tried-on product") shows nothing in preview and is easy to mistake for a generic email. Put conditions on the wording, not on the image. A flow that is trigger → delay → one store email, with the try-on only inside a template `{% if %}`, is not an Antla flow; it was rejected for exactly that reason.

**Never email the uploaded photo.** `antla_user_image_url` is the shopper's raw selfie. It is useful as a yes/no signal ("Antla can generate for this person") and should never appear in a template.

**A webhook 200 is not a delivery.** Antla answers `200 {"ok":true}` for any well-formed request and then silently drops the ones it can't fulfil: unknown product, no photo on file for that email, a product the campaign can't style, a paused campaign, even a wrong token. The only proof is the campaign event arriving on the profile, typically about ten seconds later. A 400 always means the payload is wrong, usually an empty product ID or `product_id` written instead of `productId`.

**Send people Antla can generate for, and give everyone else a path.** Gate a webhook branch on `properties['antla_user_image_url']` being set, and on nothing else. People who fail the gate should get the normal version of the message, not silence. So should people who pass the gate but for whom no look arrives.

**Know what the campaign generates before promising it.** A campaign set to "1 recommendation" or "Multiple" returns looks for *other* products, so a shopper who abandoned product A is shown product B. For cart and browse recovery the merchant usually expects the same product, which needs a campaign set to "Their photo" in the Antla app. Check a recent real event on the campaign metric and tell the user what it actually returns.

**No finished flow without a read-back.** Klaviyo can store something different from what was sent, without an error. See `references/verification.md`.

**No loops.** A webhook for campaign X produces metric X. Don't put that webhook in a flow triggered by metric X.

**One flow per trigger per purpose.** Before going live, find every live flow on the same trigger. The common collisions are a new abandoned-checkout flow beside the store's existing one, and a custom flow on a campaign metric beside the flow Antla created for it. Both mean double sends.

**Throttle re-entry.** The try-on metric fires on every try-on and keen shoppers do many in a row. Give flows on it a "not in this flow in the last N days" filter.

**Don't re-check Antla's eligibility rules** inside flows triggered by Antla campaign events. Antla has already checked that the shopper is logged in and subscribed; duplicating those checks just hides shoppers.

## Limits of the Klaviyo MCP worth knowing

- A flow's structure can't be edited after creation. `update_flow` changes status only, and it applies that status to **every action in the flow**, including ones that were deliberately left in draft. `update_flow_action` edits a single action. To restructure, create a new flow and retire the old one, or have the user edit in Klaviyo.
- Putting a flow in draft is the "off" switch; there is no paused state. People waiting in a delay will not receive later messages while it is in draft.
- SMS actions fail with `403 Text message actions are not enabled for this company` on accounts without SMS set up. Build email-only and say so.
- Attaching a `template_id` to a flow email clones the template. Edit the flow's copy, not the library original, to change what the flow sends.
- Antla-created templates are drag-and-drop (`SYSTEM_DRAGGABLE`) and their HTML is long. Prefer creating a new CODE template from `assets/` over rewriting theirs.
- Klaviyo's generic preview has no Antla event data. Use `render_email_template` with a context you supply, or have the user send "Test email" from Antla's flow builder.

## When a shopper didn't get the email

Work down this list; stop at the first thing that is false.

1. Antla shows the integration enabled, and the Antla flow is live.
2. The matching Klaviyo flow **and its email action** are live (a live flow can contain a draft email).
3. For Antla-triggered events: the shopper was logged in and is subscribed to email marketing. Guest try-ons never trigger campaign events.
4. The product matched the Antla flow's audience rule.
5. The campaign event exists on the profile (`get_events` filtered by the campaign metric). If it doesn't, the problem is before Klaviyo; if it does, the problem is in the flow.
6. For webhook-driven sends: the shopper has `antla_user_image_url`; the rendered body had a real product ID; the token in the URL matches the campaign.
7. Flow filters and Smart Sending: an order placed since entry, a "not in flow recently" filter, or a recent message can each skip the send.

## Files in this skill

- `references/data-reference.md`: every Antla metric property, profile property and template variable; product ID paths for common triggers; template syntax that is known to render.
- `references/webhook.md`: the webhook contract, a table of tested responses, loop safety and the test procedure.
- `references/flow-recipes.md`: `create_flow` building blocks and five complete recipes, segment definitions, and an error table.
- `references/verification.md`: the verification pass to run after building anything. Read it every time.
- `references/flow-map.md`: the flow map page: what it shows, how to gather it, the spec for `scripts/build_flow_map.py`.
- `references/playbook.md`: twelve things to build, design and copy guidance, and what requires the Antla app.
- `scripts/build_flow_map.py`: builds the flow map page from a JSON spec.
- `assets/flow-map-template.html`: the flow map page design (Antla grid style, light and dark).
- `scripts/verify_flow.py`: checks a flow as read back from Klaviyo and prints every path a shopper can take, plus errors and warnings.
- `assets/tryon-reminder.html`: email for flows triggered by the try-on metric.
- `assets/looks-lookbook.html`: email for flows triggered by any Antla campaign event; handles one look, several looks, the original try-on and an optional discount.
- `assets/lookbook-followup.html`: the second email in a campaign-event series; shows the same products as catalog photos so it doesn't repeat the generated images.
- `assets/browse-reminder.html`: plain browse reminder with a "see it on you" link, for Viewed Product flows; the fallback when no personalised look can be sent.
- `assets/post-purchase-invite.html`: post-purchase email with no personal image, with different copy for shoppers who have and haven't tried on.
- `assets/product-reminder-tryon.html`: fallback reminder for Added to Cart, Checkout Started, Viewed Product and back-in-stock flows when the merchant has no template of their own; catalog photo plus a "See it on you" link, and the shopper's own try-on only when it is the same product. Not a try-on email: use `cart-own-tryon.html` or a campaign webhook for that.
- `assets/cart-own-tryon.html`: cart/checkout email for the "tried on recently" branch; the shopper's latest try-on is always the hero (visible in Klaviyo's preview), headline names the cart item when it matches.
- `assets/winback-tryon.html`: win-back email from profile properties; latest try-on if there is one, otherwise a try-on invite.
- `assets/profile-hero-block.html`: a hero block for any campaign that shows the shopper's latest try-on, with a fallback for everyone else.
