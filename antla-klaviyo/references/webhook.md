# The Antla campaign webhook

Each flow created in the Antla app has a webhook URL. POSTing a shopper's email and a product ID to it asks Antla to generate that campaign's content for that shopper and send the campaign event to Klaviyo. This is what lets a flow that Antla does not trigger (abandoned checkout, browse abandonment, post-purchase, win-back) still end in a personalised try-on email.

## The round trip

```
Klaviyo flow A (any trigger)
   └─ webhook action ──POST──▶ Antla campaign <token>
                                  └─ generates look(s) on the shopper's photo
                                  └─ sends "Antla Campaign Event: <name> [<token>]" to Klaviyo
Klaviyo flow B (triggered by that metric)
   └─ email using {{ event.antla_looks… }}
```

Flow A decides who and when. The Antla campaign decides what is generated (email type, audience, discount). Flow B decides how it looks and what follows. Flow B usually already exists, because Antla creates it when the campaign is set live.

A flow webhook is one-way. Klaviyo cannot read Antla's response into the same flow, so flow A can never show the generated image itself; only flow B can.

Flow A can, however, see whether flow B's trigger arrived: a conditional split on "has received the campaign metric in the last hour" after a short wait. Always add that check and a fallback email after a webhook (the block is in `flow-recipes.md`), because of the silent drops described below.

The event arriving still isn't the email. Flow B sends it, after the time gap the merchant set for the campaign in Antla, and flow B can skip it: Smart Sending on its email, a flow filter, an email action left in draft. A shopper skipped there gets neither the look nor flow A's fallback. Read flow B's definition before pointing a webhook at its campaign, tell the user what could skip the send, and where it matters use the stricter "received an email from the campaign's flow" check in `flow-recipes.md`.

## Where the URL comes from

Every campaign's URL has the same shape:

```
https://app-antla.com/integrations/klaviyo/webhook/<16-character token>
```

and the token is the one in the campaign's metric name, `Antla Campaign Event: <name> [<token>]`. So there are two ways to get it, and both end in the same check:

- **From the account.** Pick the campaign from the inventory (SKILL.md step 1b) and build the URL from its metric name. Say the campaign's name back to the user before using it.
- **From the merchant.** They copy it from Antla app → Integrations → Klaviyo → open the flow → webhook section.

**Validate every URL before building with it, pasted or built.** Take the last 16 characters and look for them in the account's Antla metric names (`get_metrics` with `filter: equals(integration.name,"Antla")`). 
- A match tells you which campaign, metric and flow the webhook feeds; say the campaign's name back to the user so they can confirm it is the one they meant.
- No match means the URL was mistyped, cut short, or belongs to another store. Stop and ask for it again. Antla answers a wrong token with `200 {"ok":true}` and then ignores the request, so nothing downstream will reveal the mistake.
- Also check the shape: `https://app-antla.com/integrations/klaviyo/webhook/` followed by exactly 16 lowercase hex characters, with no trailing spaces or punctuation picked up in the paste.

Do not point a flow at a campaign just because its URL is to hand: each campaign generates different content, so choose the one whose output fits the flow and confirm it with the user. If no campaign fits, the merchant has to create one in the Antla app first.

**The token is the only authentication, and it is not well hidden.** It appears in the metric name, so anyone who can read the Klaviyo account's metrics can call the webhook, and a call sends a real email to a real shopper. Keep that exposure from growing: never write a full URL or full token into a hand-over, flow map, ticket or chat message (campaign name plus the first 8 characters is enough to identify it), and never commit one to a repository. If a URL has leaked, the merchant deletes that webhook in the Antla app; point any flow that used it at a new one.

## Request

```
POST <webhook url>
Content-Type: application/json

{
  "email": "{{ person.email|default:'' }}",
  "productId": "{{ event.extra.line_items.0.product_id|default:'' }}"
}
```

| Field | Required | Notes |
|---|---|---|
| `email` | yes | Must belong to an existing Klaviyo profile. Not case-sensitive. |
| `productId` | yes | Numeric Shopify product ID (as a string or a number) or a `gid://shopify/Product/…` GID. Exact camelCase. |

Send only these two fields. Antla generates on the photo the shopper already uploaded; a flow never supplies a photo of its own.

Choose the `productId` path from the table in `data-reference.md` for the flow's trigger.

## Observed behaviour (tested against the live endpoint)

| Request | Response | What happens |
|---|---|---|
| Valid email + numeric product ID | `200 {"ok":true}` | Campaign event arrived in Klaviyo about 10 seconds later. |
| Valid email + GID product ID | `200 {"ok":true}` | Same. |
| Product ID sent as an unquoted number | `200 {"ok":true}` | Same. |
| Email in different letter case | `200 {"ok":true}` | Same. |
| Extra unknown fields | `200 {"ok":true}` | Ignored. |
| Missing or empty `email` | `400 {"ok":false,"error":"Invalid webhook request"}` | |
| Missing or empty `productId` | `400` same error | This is what a wrong template path produces, because the variable renders empty. |
| `product_id` (snake_case) instead of `productId` | `400` same error | A common mistake. |
| Product handle instead of an ID | `400` same error | |
| Form-encoded body, malformed JSON | `400` same error | Must be JSON. |
| GET | `400` | POST only. |
| **Product ID that doesn't exist** | **`200 {"ok":true}`** | **No event. Dropped silently.** |
| **Email with no Klaviyo profile / no photo on file** | **`200 {"ok":true}`** | **No event, no profile created.** |
| **A real product the campaign can't use** | **`200 {"ok":true}`** | **No event.** Seen with a product outside what the campaign could style. |
| **Wrong or unknown token** | **`200 {"ok":true}`** | **No event.** |

**A 200 only means the request was well-formed and queued.** Antla does the work afterwards and drops requests it can't fulfil without telling the caller. Per Antla, requests for paused, draft or removed campaigns are also ignored, and so are requests for shoppers who fail Antla's own consent and eligibility checks. So a 4xx tells you the payload is wrong, and a 200 tells you nothing about delivery. The only proof is the campaign event appearing on the profile.

Retry on 5xx. Do not retry a 4xx; fix the payload.

## Who will actually get an email

For a webhook call to turn into an event, the shopper needs a photo on file with Antla (they have tried something on before) and the product must be one the campaign can generate for. In Klaviyo terms, that is profiles where `properties['antla_user_image_url']` is set.

Gate the webhook branch on that, and on nothing else, so everyone else can take a normal path instead of silently receiving nothing. Antla runs its own consent and eligibility checks on webhook requests, exactly as it does for try-on events, and silently drops the ones that fail; the fallback email covers those shoppers, so the flow does not re-check consent.

## Avoiding loops

A webhook that fires campaign X produces metric X. If the flow containing that webhook is itself triggered by metric X, it triggers itself forever. Before adding a webhook, check the trigger of the flow it sits in:
- triggered by a Shopify or Klaviyo metric → safe;
- triggered by a different Antla campaign's metric → safe, but trace the chain to make sure it doesn't come back round;
- triggered by the same campaign's metric → do not build it.

Also watch for a quieter version: flow A's webhook produces an email from flow B, and flow A then also sends its own email. Decide which one the shopper should get and end the other path.

## Testing a webhook

1. Ask the user which email address to test with (their own, with a try-on already done on the store so a photo is on file) and which product.
2. Tell them what will happen: if the campaign's Klaviyo flow is live, a real email goes to that address.
3. POST the payload exactly as Klaviyo would render it:
   ```bash
   curl -sS -X POST '<webhook url>' -H 'Content-Type: application/json' \
     --data '{"email":"<address>","productId":"<product id>"}' -w '\nHTTP %{http_code}\n'
   ```
4. Wait about 15 seconds, then look for the event: `get_events` with `filter: equals(metric_id,"<campaign metric id>"),greater-or-equal(datetime,<just before the call, ISO UTC>)`, `sort: -datetime`. Limit `fields_event` to what you need, for example `event_properties.antla_original_product.product_title` and `event_properties.antla_looks`.
5. Check that `antla_original_product` is the product you sent and that `antla_looks` (or `antla_original_tryon_image_url`) is populated. If nothing arrives within a minute, work through the silent-drop causes above rather than resending repeatedly.

This tests Antla's side and the payload. It does not test the Klaviyo flow that will send the webhook; that only runs when its real trigger fires while the flow is live.

After a live flow has sent a webhook, some accounts record a `Webhook Send Successful` metric on the profile with `request_body`, `destination_url` and `response_status`. When present, it is the quickest way to see exactly what Klaviyo sent.
