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

## Where the URL comes from

Only the merchant can get it: Antla app → Integrations → Klaviyo → open the flow → webhook section. It looks like

```
https://app-antla.com/integrations/klaviyo/webhook/<16-character token>
```

The token matches the token in the metric name `Antla Campaign Event: <name> [<token>]`.

**Validate every pasted URL before building with it.** Take the last 16 characters and look for them in the account's Antla metric names (`get_metrics` with `filter: equals(integration.name,"Antla")`). 
- A match tells you which campaign, metric and flow the webhook feeds; say the campaign's name back to the user so they can confirm it is the one they meant.
- No match means the URL was mistyped, cut short, or belongs to another store. Stop and ask for it again. Antla answers a wrong token with `200 {"ok":true}` and then ignores the request, so nothing downstream will reveal the mistake.
- Also check the shape: `https://app-antla.com/integrations/klaviyo/webhook/` followed by exactly 16 lowercase hex characters, with no trailing spaces or punctuation picked up in the paste.

If the user has not given a URL, ask for it. Do not reuse one found on an existing flow for a different purpose without saying so, since each campaign generates different content.

The token is the only authentication. Treat the URL like a password: don't paste it into public places.

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
| `userImageUrl` | no | A photo of the shopper. When omitted, Antla uses the photo already on file for that shopper. |

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

**A 200 only means the request was well-formed and queued.** Antla does the work afterwards and drops requests it can't fulfil without telling the caller. Per Antla, requests for paused, draft or removed campaigns are also ignored. So a 4xx tells you the payload is wrong, and a 200 tells you nothing about delivery. The only proof is the campaign event appearing on the profile.

Retry on 5xx. Do not retry a 4xx; fix the payload.

## Who will actually get an email

For a webhook call to turn into an event, the shopper needs a photo Antla can use (they have tried something on before, or `userImageUrl` is supplied) and the product must be one the campaign can generate for. In Klaviyo terms, the safe audience is profiles where `properties['antla_user_image_url']` is set. Gate the webhook branch on that, and on nothing else, so everyone else can take a normal path instead of silently receiving nothing.

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
