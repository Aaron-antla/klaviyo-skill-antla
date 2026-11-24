# Flow recipes for the Klaviyo MCP

Building blocks and complete definitions for `create_flow`. Every pattern here was accepted by the Klaviyo API, and recipes A, C, D and E were read back from Klaviyo and matched link for link. Placeholders in `<ANGLE_BRACKETS>` must be replaced with values from the target account; metric IDs are different in every account.

## Contents
1. Rules of `create_flow`
2. Building blocks (trigger filters, profile filters, splits, actions)
3. Recipe A: abandoned checkout with a try-on split
4. Recipe B: try-on reminder
5. Recipe C: browse abandonment → personal look
6. Recipe D: post-purchase "complete the look"
7. Recipe E: lookbook follow-up series on a campaign event
8. Segments
9. Errors you will meet

---

## 1. Rules of `create_flow`

- The body is `{ "data": { "type": "flow", "attributes": { "name": "…", "definition": { … } } } }`.
- `definition` needs `triggers` (exactly one), `actions`, and `entry_action_id`.
- New actions use `temporary_id` (any string) and link to each other by those IDs. Never send `id` on create.
- Links: most actions use `"links": {"next": "<temporary_id or null>"}`. `conditional-split` and `trigger-split` use `{"next_if_true": …, "next_if_false": …}`. `multi-branch-split` puts a `links.next` on each branch. `null` ends the path.
- A new flow is created with status `draft` and so is every action in it. Leave it that way until the user asks to go live.
- Ask for a small response: `fields_flow: ["id","name","status"]`. Request the definition only when you need to read it back.
- Filters: **condition groups are ANDed; conditions inside one group are ORed.** To require two things, use two groups.
- When an email action is given a `template_id`, Klaviyo clones the template into the flow and returns a new ID. Later edits to the library template do not change the flow's copy.
- **Flows are trees.** Two paths may share a later step in only one tested case: one branch of a split runs an action and then continues into the step its sibling branch goes to directly ("yes → webhook → delay", "no → delay"). Branches of *different* splits pointing at one shared step are not safe: Klaviyo has silently stored those links as `null` (the create call still succeeded) and has also returned a 500. When paths need the same later steps, give each path its own copy.
- **Read every flow back after creating it** and compare action and link counts and every path with what you intended. This is `verification.md`; it is not optional.
- There is no "edit flow structure" call. `update_flow` only changes status (and it sets **every action** in the flow to that status). `update_flow_action` edits one action. To restructure a flow, create a new one and retire the old.

## 2. Building blocks

### Trigger on a metric, with a filter on event properties

```json
{"type": "metric", "id": "<TRIED_ON_METRIC_ID>", "trigger_filter": {"condition_groups": [
  {"conditions": [{"type": "metric-property", "metric_id": "<TRIED_ON_METRIC_ID>", "field": "antla_test_event",
    "filter": {"type": "boolean", "operator": "equals", "value": false}}]}
]}}
```

Other useful event-property filters:

```json
{"type": "metric-property", "metric_id": "<ID>", "field": "antla_tryon_count", "filter": {"type": "numeric", "operator": "greater-than-or-equal", "value": 3}}
{"type": "metric-property", "metric_id": "<ID>", "field": "antla_product_category", "filter": {"type": "string", "operator": "equals", "value": "Dresses"}}
{"type": "metric-property", "metric_id": "<ID>", "field": "antla_looks", "filter": {"type": "list", "operator": "length-greater-than-or-equal", "value": 2}}
{"type": "metric-property", "metric_id": "<ID>", "field": "antla_discount.code", "filter": {"type": "existence", "operator": "is-set"}}
```

The last two (list length, and a dotted path into a nested object) were accepted by the API but not yet observed evaluating on a live event. Test both branches before relying on them.

### Flow-level profile filter (checked at entry and before every action)

```json
"profile_filter": {"condition_groups": [
  {"conditions": [{"type": "profile-metric", "metric_id": "<PLACED_ORDER_METRIC_ID>", "measurement": "count",
    "measurement_filter": {"type": "numeric", "operator": "equals", "value": 0},
    "timeframe_filter": {"type": "date", "operator": "flow-start"}, "metric_filters": null}]},
  {"conditions": [{"type": "profile-not-in-flow", "timeframe_filter": {"type": "date", "operator": "in-the-last", "unit": "day", "quantity": 7}}]}
]}
```

The first group drops anyone who orders after entering. The second stops the same person re-entering within 7 days; leave it out while testing, because it blocks repeat test runs.

Profile-property conditions (usable in the flow filter, splits and segments):

```json
{"type": "profile-property", "property": "properties['antla_user_image_url']", "filter": {"type": "existence", "operator": "is-set"}}
{"type": "profile-property", "property": "properties['antla_has_tried_on']", "filter": {"type": "boolean", "operator": "equals", "value": true}}
{"type": "profile-property", "property": "properties['antla_tryon_count']", "filter": {"type": "numeric", "operator": "greater-than-or-equal", "value": 5}}
```

### "Has done X recently" split

```json
{"temporary_id": "split-tryon", "type": "conditional-split", "data": {"profile_filter": {"condition_groups": [{"conditions": [
  {"type": "profile-metric", "metric_id": "<TRIED_ON_METRIC_ID>", "measurement": "count",
   "measurement_filter": {"type": "numeric", "operator": "greater-than", "value": 0},
   "timeframe_filter": {"type": "date", "operator": "in-the-last", "unit": "hour", "quantity": 24}, "metric_filters": null}
]}]}}, "links": {"next_if_true": "webhook-antla", "next_if_false": "delay-email"}}
```

Timeframe units are `hour`, `day`, `week`. Use `{"type": "date", "operator": "flow-start"}` for "since entering this flow".

### Split on the triggering event's own properties

```json
{"temporary_id": "split-looks", "type": "trigger-split", "data": {"trigger_type": "metric", "trigger_id": "<CAMPAIGN_METRIC_ID>",
  "trigger_filter": {"condition_groups": [{"conditions": [
    {"type": "metric-property", "metric_id": "<CAMPAIGN_METRIC_ID>", "field": "antla_looks", "filter": {"type": "list", "operator": "length-greater-than-or-equal", "value": 2}}
  ]}]}}, "links": {"next_if_true": "email-multi", "next_if_false": "email-single"}}
```

### Three-way split

```json
{"temporary_id": "split-photo", "type": "multi-branch-split", "data": {"name": "Has a try-on photo?", "branches": [
  {"branch_id": "b-photo", "name": "Photo on file", "order": 0, "branch_filter": {"condition_groups": [
    {"conditions": [{"type": "profile-property", "property": "properties['antla_user_image_url']", "filter": {"type": "existence", "operator": "is-set"}}]}
  ]}, "links": {"next": "webhook-antla"}},
  {"branch_id": "b-tried", "name": "Tried on, no photo on file", "order": 1, "branch_filter": {"condition_groups": [
    {"conditions": [{"type": "profile-property", "property": "properties['antla_has_tried_on']", "filter": {"type": "boolean", "operator": "equals", "value": true}}]}
  ]}, "links": {"next": "email-plain"}},
  {"branch_id": "b-else", "is_else": true, "links": {"next": "email-invite"}}
]}}
```

### Webhook action

```json
{"temporary_id": "webhook-antla", "type": "send-webhook", "data": {"message": {
  "name": "Antla: generate look",
  "url": "<ANTLA_WEBHOOK_URL>",
  "headers": {"Content-Type": "application/json"},
  "body": "{\n  \"email\": \"{{ person.email|default:'' }}\",\n  \"productId\": \"{{ <PRODUCT_ID_PATH>|default:'' }}\"\n}"
}, "status": "draft"}, "links": {"next": null}}
```

`<PRODUCT_ID_PATH>` depends on the trigger; see `data-reference.md` section 4.

### Webhook with fallback (use this every time a webhook is sent)

Antla drops requests it can't fulfil without an error, so a webhook must never be the last step. Wait, check whether the campaign event arrived, and send the normal email if it didn't.

```json
{"temporary_id": "webhook-antla", "type": "send-webhook", "data": {"message": { "…": "as above" }, "status": "draft"}, "links": {"next": "delay-wait"}},
{"temporary_id": "delay-wait", "type": "time-delay", "data": {"unit": "minutes", "value": 30}, "links": {"next": "split-arrived"}},
{"temporary_id": "split-arrived", "type": "conditional-split", "data": {"profile_filter": {"condition_groups": [{"conditions": [
  {"type": "profile-metric", "metric_id": "<CAMPAIGN_METRIC_ID>", "measurement": "count",
   "measurement_filter": {"type": "numeric", "operator": "greater-than", "value": 0},
   "timeframe_filter": {"type": "date", "operator": "in-the-last", "unit": "hour", "quantity": 1}, "metric_filters": null}
]}]}}, "links": {"next_if_true": null, "next_if_false": "email-fallback"}},
{"temporary_id": "email-fallback", "type": "send-email", "data": {"message": { "…": "the normal version of this message" }, "status": "draft"}, "links": {"next": null}}
```

`<CAMPAIGN_METRIC_ID>` is the metric whose name contains the webhook's token. "In the last hour" is tighter than "since flow start" and avoids counting a campaign event the shopper received for some other reason days earlier.

**The event proves Antla generated a look, not that the shopper was emailed.** The email is sent by the campaign's own flow, which can still skip it. So before using this block, read that flow's definition and check: its email action is live; whether Smart Sending is on (if it is, a shopper who received any email in the Smart Sending window gets neither the look nor the fallback, so tell the user and let them decide whether to turn it off on that email); what flow filters it has; and how long it waits before sending. That wait is the time gap the merchant set for the campaign in Antla, so a shopper on the "look arrived" path gets the look email that much later, not at the moment the event lands. Say the gap back to the user when describing the flow.

A stricter check tests for the send itself: replace the condition above with "received an email from the campaign's flow".

```json
{"type": "profile-metric", "metric_id": "<RECEIVED_EMAIL_METRIC_ID>", "measurement": "count",
 "measurement_filter": {"type": "numeric", "operator": "greater-than", "value": 0},
 "timeframe_filter": {"type": "date", "operator": "in-the-last", "unit": "hour", "quantity": 1},
 "metric_filters": [{"property": "$flow", "filter": {"type": "string", "operator": "equals", "value": "<CAMPAIGN_FLOW_ID>"}}]}
```

`<RECEIVED_EMAIL_METRIC_ID>` is Klaviyo's own `Received Email` metric, and its `$flow` property holds the ID of the flow that sent the email (confirmed on a real event). `create_flow` accepted this condition and stored it unchanged in a draft flow; it has not yet been watched evaluating on a live flow, so check which branch the first real shopper takes. Because the campaign's flow sends after the merchant's time gap, the wait in front of this check must be longer than that gap (read the delay in the campaign flow's definition and add a margin), or every shopper gets both emails. If the gap is long enough that the fallback would arrive too late to be useful, keep the event check instead.

### Email action

```json
{"temporary_id": "email-1", "type": "send-email", "data": {"message": {
  "name": "Try-on reminder",
  "from_email": "<SENDER_EMAIL>", "from_label": "<SENDER_NAME>",
  "subject_line": "You in the {{ event.antla_product_title }}",
  "preview_text": "You tried it on. It looked good.",
  "template_id": "<TEMPLATE_ID>",
  "smart_sending_enabled": true
}, "status": "draft"}, "links": {"next": "delay-2"}}
```

Get the sender defaults from `get_account_details` (`contact_information.default_sender_email` and `default_sender_name`).

### Delay and profile update

```json
{"temporary_id": "delay-1", "type": "time-delay", "data": {"unit": "hours", "value": 4}, "links": {"next": "split-checkout"}}

{"temporary_id": "tag-explorer", "type": "update-profile", "data": {"profile_operations": [
  {"operator": "create", "property_type": "boolean", "property_key": "properties['Antla Style Explorer']", "property_value": true}
], "status": "draft"}, "links": {"next": null}}
```

Delay units are `minutes`, `hours`, `days`. The `property_key` must be written `properties['Name']`; a bare name is rejected. Date properties accept `"property_type": "date", "property_value": "today"`.

---

## 3. Recipe A: abandoned checkout with a try-on split

Shoppers Antla can generate for get a personalised look; everyone else, and anyone for whom no look arrives, gets the normal reminder. Six actions, six links.

Paths:
1. photo on file → webhook → wait → look arrived → end (the campaign's flow sends the email, after the time gap the merchant set in Antla)
2. photo on file → webhook → wait → no look → normal cart email
3. no photo on file → wait → normal cart email

```json
{"triggers": [{"type": "metric", "id": "<CHECKOUT_STARTED_METRIC_ID>", "trigger_filter": null}],
 "profile_filter": {"condition_groups": [
   {"conditions": [{"type": "profile-metric", "metric_id": "<PLACED_ORDER_METRIC_ID>", "measurement": "count", "measurement_filter": {"type": "numeric", "operator": "equals", "value": 0}, "timeframe_filter": {"type": "date", "operator": "flow-start"}, "metric_filters": null}]},
   {"conditions": [{"type": "profile-not-in-flow", "timeframe_filter": {"type": "date", "operator": "in-the-last", "unit": "day", "quantity": 1}}]}]},
 "entry_action_id": "delay-entry",
 "actions": [
  {"temporary_id": "delay-entry", "type": "time-delay", "data": {"unit": "hours", "value": 1}, "links": {"next": "split-photo"}},
  {"temporary_id": "split-photo", "type": "conditional-split", "data": {"profile_filter": {"condition_groups": [
     {"conditions": [{"type": "profile-property", "property": "properties['antla_user_image_url']", "filter": {"type": "existence", "operator": "is-set"}}]}]}},
   "links": {"next_if_true": "webhook-antla", "next_if_false": "delay-email"}},
  {"temporary_id": "webhook-antla", "type": "send-webhook", "data": {"message": {"name": "Antla try-on webhook", "url": "<ANTLA_WEBHOOK_URL>", "headers": {"Content-Type": "application/json"}, "body": "{\n  \"email\": \"{{ person.email|default:'' }}\",\n  \"productId\": \"{{ event.extra.line_items.0.product_id|default:'' }}\"\n}"}, "status": "draft"}, "links": {"next": "delay-email"}},
  {"temporary_id": "delay-email", "type": "time-delay", "data": {"unit": "hours", "value": 19}, "links": {"next": "split-arrived"}},
  {"temporary_id": "split-arrived", "type": "conditional-split", "data": {"profile_filter": {"condition_groups": [{"conditions": [{"type": "profile-metric", "metric_id": "<CAMPAIGN_METRIC_ID>", "measurement": "count", "measurement_filter": {"type": "numeric", "operator": "greater-than", "value": 0}, "timeframe_filter": {"type": "date", "operator": "flow-start"}, "metric_filters": null}]}]}}, "links": {"next_if_true": null, "next_if_false": "email-cart"}},
  {"temporary_id": "email-cart", "type": "send-email", "data": {"message": {"name": "Abandoned cart email", "from_email": "<SENDER_EMAIL>", "from_label": "<SENDER_NAME>", "subject_line": "Your cart is waiting", "preview_text": "Everything you picked is still here.", "template_id": "<EXISTING_ABANDONED_CART_TEMPLATE_ID>", "smart_sending_enabled": false}, "status": "draft"}, "links": {"next": null}}
 ]}
```

This is the one place two paths share a step (the webhook branch rejoins its sibling's delay). It has been read back intact. Because the check is shared, a shopper on path 3 who happened to receive that campaign's event from somewhere else since entering would get no cart email; if that matters, give each branch its own delay, check and email instead.

Before going live: the account almost certainly has an abandoned checkout flow already on the same trigger. Two live flows on one trigger means two messages per shopper. Set the old one to draft when this one goes live, or fold its remaining steps into this one.

Check what the campaign returns. For cart recovery the merchant expects the shopper in the item they left behind, which needs a campaign whose email type is "Their photo". A "recommendation" campaign will show a different product.

## 4. Recipe B: try-on reminder

Trigger: `Customer tried-on an outfit`, filtered to non-test events. Wait, skip anyone who has started checkout (the checkout flow owns them), then send their own image back. Template: `assets/tryon-reminder.html`.

```json
{"triggers": [{"type": "metric", "id": "<TRIED_ON_METRIC_ID>", "trigger_filter": {"condition_groups": [
   {"conditions": [{"type": "metric-property", "metric_id": "<TRIED_ON_METRIC_ID>", "field": "antla_test_event", "filter": {"type": "boolean", "operator": "equals", "value": false}}]}]}}],
 "profile_filter": {"condition_groups": [
   {"conditions": [{"type": "profile-metric", "metric_id": "<PLACED_ORDER_METRIC_ID>", "measurement": "count", "measurement_filter": {"type": "numeric", "operator": "equals", "value": 0}, "timeframe_filter": {"type": "date", "operator": "flow-start"}, "metric_filters": null}]},
   {"conditions": [{"type": "profile-not-in-flow", "timeframe_filter": {"type": "date", "operator": "in-the-last", "unit": "day", "quantity": 3}}]}]},
 "entry_action_id": "delay-1",
 "actions": [
  {"temporary_id": "delay-1", "type": "time-delay", "data": {"unit": "hours", "value": 4}, "links": {"next": "split-checkout"}},
  {"temporary_id": "split-checkout", "type": "conditional-split", "data": {"profile_filter": {"condition_groups": [{"conditions": [{"type": "profile-metric", "metric_id": "<CHECKOUT_STARTED_METRIC_ID>", "measurement": "count", "measurement_filter": {"type": "numeric", "operator": "greater-than", "value": 0}, "timeframe_filter": {"type": "date", "operator": "flow-start"}, "metric_filters": null}]}]}}, "links": {"next_if_true": null, "next_if_false": "email-1"}},
  {"temporary_id": "email-1", "type": "send-email", "data": {"message": {"name": "Try-on reminder", "from_email": "<SENDER_EMAIL>", "from_label": "<SENDER_NAME>", "subject_line": "You in the {{ event.antla_product_title }}", "preview_text": "You tried it on. It looked good.", "template_id": "<TRYON_REMINDER_TEMPLATE_ID>", "smart_sending_enabled": true}, "status": "draft"}, "links": {"next": null}}
 ]}
```

The 3-day re-entry guard matters: this metric fires on every try-on, and an engaged shopper may do ten in a sitting. Without the guard they get ten emails.

If the merchant already has an Antla-created flow of type "Their photo" for the same audience, this recipe duplicates it. Check first and customise that one instead.

## 5. Recipe C: browse abandonment → personal look

Trigger: `Viewed Product`. Everyone who doesn't progress gets an email; shoppers Antla can generate for get a personal look where one arrives. Eight actions, seven links. Fallback template: `assets/browse-reminder.html`.

Paths:
1. added to cart or started checkout → end (other flows own them)
2. photo on file → webhook → wait 30 min → look arrived → end
3. photo on file → webhook → wait 30 min → no look → browse reminder
4. no photo on file → browse reminder

```json
{"triggers": [{"type": "metric", "id": "<VIEWED_PRODUCT_METRIC_ID>", "trigger_filter": null}],
 "profile_filter": {"condition_groups": [
   {"conditions": [{"type": "profile-metric", "metric_id": "<PLACED_ORDER_METRIC_ID>", "measurement": "count", "measurement_filter": {"type": "numeric", "operator": "equals", "value": 0}, "timeframe_filter": {"type": "date", "operator": "flow-start"}, "metric_filters": null}]},
   {"conditions": [{"type": "profile-not-in-flow", "timeframe_filter": {"type": "date", "operator": "in-the-last", "unit": "day", "quantity": 7}}]}]},
 "entry_action_id": "delay-1",
 "actions": [
  {"temporary_id": "delay-1", "type": "time-delay", "data": {"unit": "hours", "value": 2}, "links": {"next": "split-progress"}},
  {"temporary_id": "split-progress", "type": "conditional-split", "data": {"profile_filter": {"condition_groups": [{"conditions": [
     {"type": "profile-metric", "metric_id": "<ADDED_TO_CART_METRIC_ID>", "measurement": "count", "measurement_filter": {"type": "numeric", "operator": "greater-than", "value": 0}, "timeframe_filter": {"type": "date", "operator": "flow-start"}, "metric_filters": null},
     {"type": "profile-metric", "metric_id": "<CHECKOUT_STARTED_METRIC_ID>", "measurement": "count", "measurement_filter": {"type": "numeric", "operator": "greater-than", "value": 0}, "timeframe_filter": {"type": "date", "operator": "flow-start"}, "metric_filters": null}]}]}},
   "links": {"next_if_true": null, "next_if_false": "split-photo"}},
  {"temporary_id": "split-photo", "type": "conditional-split", "data": {"profile_filter": {"condition_groups": [
     {"conditions": [{"type": "profile-property", "property": "properties['antla_user_image_url']", "filter": {"type": "existence", "operator": "is-set"}}]}]}},
   "links": {"next_if_true": "webhook-antla", "next_if_false": "email-reminder-plain"}},
  {"temporary_id": "webhook-antla", "type": "send-webhook", "data": {"message": {"name": "Antla: generate look for viewed product", "url": "<ANTLA_WEBHOOK_URL>", "headers": {"Content-Type": "application/json"}, "body": "{\n  \"email\": \"{{ person.email|default:'' }}\",\n  \"productId\": \"{{ event.ProductID|default:'' }}\"\n}"}, "status": "draft"}, "links": {"next": "delay-wait"}},
  {"temporary_id": "delay-wait", "type": "time-delay", "data": {"unit": "minutes", "value": 30}, "links": {"next": "split-arrived"}},
  {"temporary_id": "split-arrived", "type": "conditional-split", "data": {"profile_filter": {"condition_groups": [{"conditions": [{"type": "profile-metric", "metric_id": "<CAMPAIGN_METRIC_ID>", "measurement": "count", "measurement_filter": {"type": "numeric", "operator": "greater-than", "value": 0}, "timeframe_filter": {"type": "date", "operator": "in-the-last", "unit": "hour", "quantity": 1}, "metric_filters": null}]}]}}, "links": {"next_if_true": null, "next_if_false": "email-reminder-fallback"}},
  {"temporary_id": "email-reminder-fallback", "type": "send-email", "data": {"message": {"name": "Browse reminder (no look arrived)", "from_email": "<SENDER_EMAIL>", "from_label": "<SENDER_NAME>", "subject_line": "Still looking at {% if event.Name %}the {{ event.Name }}{% else %}this{% endif %}?", "preview_text": "It's still here, and you can see it on you.", "template_id": "<BROWSE_REMINDER_TEMPLATE_ID>", "smart_sending_enabled": true}, "status": "draft"}, "links": {"next": null}},
  {"temporary_id": "email-reminder-plain", "type": "send-email", "data": {"message": {"name": "Browse reminder (no photo on file)", "from_email": "<SENDER_EMAIL>", "from_label": "<SENDER_NAME>", "subject_line": "Still looking at {% if event.Name %}the {{ event.Name }}{% else %}this{% endif %}?", "preview_text": "It's still here, and you can see it on you.", "template_id": "<BROWSE_REMINDER_TEMPLATE_ID>", "smart_sending_enabled": true}, "status": "draft"}, "links": {"next": null}}
 ]}
```

The two reminder emails are separate actions on purpose: the paths must not share a step. In `split-progress`, two conditions inside one group are an OR.

Note the photo test is a split, not a flow filter. As a flow filter it would keep everyone else out of the flow, and they would get nothing.

## 6. Recipe D: post-purchase "complete the look"

Trigger: `Placed Order`. Three days later every buyer gets something: recommendations on their own photo where Antla can make them, otherwise an email with no personal image. Point the webhook at a campaign whose email type is "1 recommendation" or "Multiple", so the looks are other products. Eight actions, seven links. Template for the non-webhook emails: `assets/post-purchase-invite.html`.

Paths:
1. photo on file → webhook → wait 30 min → look arrived → end
2. photo on file → webhook → wait 30 min → no look → "style it" email
3. tried on, no photo on file → "style it" email
4. never tried on → try-on invite email

Structure (same building blocks as above):

```
delay 3 days
└─ multi-branch-split
   ├─ "Photo on file"         → webhook → delay 30 min → conditional-split (campaign event in the last hour?)
   │                                                      ├─ YES → end
   │                                                      └─ NO  → email (post-purchase-invite)
   ├─ "Tried on, no photo"    → email (post-purchase-invite)
   └─ ELSE                    → email (post-purchase-invite, invite subject)
```

Three separate email actions using the same template. Every branch of the multi-branch split has a `links.next`; a branch whose `links` is `null` sends that group nothing.

Webhook body: `"productId": "{{ event.extra.line_items.0.product_id|default:'' }}"`.

Add `"reentry_criteria": {"duration": 30, "unit": "day"}` to the definition so frequent buyers aren't sent this after every order.

## 7. Recipe E: lookbook follow-up series on a campaign event

Trigger: an `Antla Campaign Event: …` metric, filtered to `antla_test_event = false`. Branch on how many looks arrived and whether there is a discount, send with `assets/looks-lookbook.html`, then two days later follow up anyone who hasn't started checkout with `assets/lookbook-followup.html`, which shows the same products as catalog photos so the generated images aren't repeated. Fourteen actions, thirteen links.

```
trigger-split (antla_looks has 2 or more?)
├─ YES → email "several looks" → delay 2d → split (started checkout since entering?) ─ NO → follow-up email
└─ NO  → trigger-split (antla_discount.code is set?)
         ├─ YES → email "one look + discount" → delay 2d → split (started checkout?) ─ NO → follow-up email
         └─ NO  → email "one look"            → delay 2d → split (started checkout?) ─ NO → follow-up email
```

**Each of the three first emails has its own delay, split and follow-up email.** Pointing all three at one shared delay looks tidier and does not work: Klaviyo kept the link for one branch and silently nulled the other two, so two thirds of shoppers never got the follow-up.

The follow-up condition is "has not started checkout since entering", not "clicked an email", because a click count also matches clicks on unrelated emails. The flow filter already removes anyone who orders.

Subject lines that use the event:
```
{% if person.first_name %}{{ person.first_name }}, we{% else %}We{% endif %} styled {{ event.antla_looks|length }} looks on you
You in the {% if event.antla_looks.0.product_title %}{{ event.antla_looks.0.product_title }}{% else %}{{ event.antla_original_product.product_title }}{% endif %}, with {{ event.antla_discount.percentage }}% off
```

The second one uses `{% if %}` rather than `|default:` on purpose: `default:` with a variable as its argument makes Klaviyo fail the whole render.

**This shares a trigger with the flow Antla created for the same campaign.** Never have both live. Either edit Antla's flow in the Klaviyo editor (its structure can't be changed through the MCP), or build the richer flow, confirm it with the user, then put Antla's original in draft.

## 8. Segments

`create_or_update_segment` uses the same condition shapes. State the logic to the user in plain AND/OR words before creating a segment.

Tried on in the last 30 days and has not ordered in that time:
```json
{"condition_groups": [
  {"conditions": [{"type": "profile-metric", "metric_id": "<TRIED_ON_METRIC_ID>", "measurement": "count", "measurement_filter": {"type": "numeric", "operator": "greater-than", "value": 0}, "timeframe_filter": {"type": "date", "operator": "in-the-last", "unit": "day", "quantity": 30}, "metric_filters": null}]},
  {"conditions": [{"type": "profile-metric", "metric_id": "<PLACED_ORDER_METRIC_ID>", "measurement": "count", "measurement_filter": {"type": "numeric", "operator": "equals", "value": 0}, "timeframe_filter": {"type": "date", "operator": "in-the-last", "unit": "day", "quantity": 30}, "metric_filters": null}]}
]}
```

Ready for personal looks (photo on file):
```json
{"condition_groups": [
  {"conditions": [{"type": "profile-property", "property": "properties['antla_user_image_url']", "filter": {"type": "existence", "operator": "is-set"}}]}
]}
```

Other useful ones: heavy try-on users (`antla_tryon_count` ≥ 5, zero orders all time), category fans (`antla_last_tryon_category` equals a category), and never tried on (`antla_has_tried_on` not set), which is the audience for a "see it on you" campaign.

## 9. Errors you will meet

| Error | Cause | Fix |
|---|---|---|
| `403 Text message actions are not enabled for this company` | The flow contains a `send-sms` action and SMS isn't set up for API use on the account. | Remove the SMS action and tell the user; they can add SMS in the Klaviyo editor. |
| `400 All custom profile properties must be of the form: properties['property name']` | A bare `property_key` on an `update-profile` action. | Write `properties['Name']`. |
| Everyone takes the non-webhook branch; the webhook never fires | The split gates on something other than `antla_user_image_url`, or on a value no profile in the account has. | Gate on `antla_user_image_url` only, and confirm real profiles pass it. |
| Look event arrives but the shopper gets no email at all | The campaign's own flow skipped the send (Smart Sending, a flow filter, a draft email), and the fallback was skipped because the event exists. | Read the campaign's flow; turn Smart Sending off on its email if the user agrees, or use the stricter "received an email from the campaign's flow" check. |
| `verify_flow.py` warns that `productId` is a fixed value | The webhook body has a literal product ID. | Intended for a single-product send (new arrival, win-back). Anywhere else, use the trigger's product variable. |
| Webhook returns 400 at send time | The product ID variable rendered empty, or the key isn't exactly `productId`. | Check the path against a real event for that trigger. |
| `create_flow` succeeds but some paths end early | Links where separate branches converged on one step were stored as `null`. | Give each path its own copy of the shared steps, recreate, and read back. |
| `create_flow` returns 500 with no useful detail | Often the same cause: branches merging into one action. | Remove the merge; duplicate the action per branch. |
| A branch of a multi-branch split does nothing | Its `links` is `null` or missing. | Give every branch a `links.next`, or state why that group gets nothing. |
| Email renders with a broken image | The template is in a flow not triggered by an Antla metric, or the campaign's email type doesn't supply that field. | Guard images with `{% if %}`; match the template to the trigger. |
| `render_email_template` returns `text: null` | CODE templates have no plaintext version unless you supply one. | Request `fields_template: ["html"]`. |
