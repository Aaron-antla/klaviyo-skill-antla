# Antla data in Klaviyo: full reference

Everything here was read from a live Klaviyo account with Antla connected, or from Antla's help centre. Metric IDs differ per account, so look them up by name; never reuse an ID from another account or from this file.

## Contents
1. Metric: `Customer tried-on an outfit`
2. Metrics: `Antla Campaign Event: <name> [<token>]`
3. Profile properties
4. Where the product ID lives on common Shopify triggers
5. Template syntax notes

---

## 1. Metric: `Customer tried-on an outfit`

Fires on every completed try-on that Antla can tie to a Klaviyo profile. It carries the image the shopper actually generated. One event per try-on.

| Property | Example | Notes |
|---|---|---|
| `antla_tryon_image_url` | `https://…/generations/…jpg` | The generated image of the shopper wearing the product. |
| `antla_user_image_url` | `https://cdn.app-antla.com/users_uploads/…jpg` | The shopper's own uploaded photo. Never put this in an email; it is the raw input, not a styled result. |
| `antla_product_title` | `Plain White Tee` | |
| `antla_product_handle` | `plain-white-tee` | Build the product link as `<store url>/products/<handle>`. The event has no product URL. |
| `antla_product_id` | `{ "id": "gid://shopify/Product/123", "title": "…" }` | An object. Use `event.antla_product_id.id`. |
| `antla_product_image_url` | catalog image URL | The normal product photo. |
| `antla_product_category` | `T-Shirts` | Antla's category for the product. Good for splits. |
| `antla_tryon_count` | `160` | Lifetime try-ons for this shopper, including this one. |
| `antla_tried_on_products` | `[{ "id": "gid://…", "handle": "…" }, …]` | Every product tried on, newest first. A list of objects. |
| `antla_tryon_at` | ISO timestamp | |
| `antla_test_event` | `false` | `true` for test events sent from the Antla app. |
| `antla_shop_domain` | `xxxx.myshopify.com` | The admin domain, not the public storefront domain. Do not link to it. |
| `antla_klaviyo_campaign_label`, `antla_tryon_id`, `antla_tryon_uuid`, `antla_shop_id` | | Internal identifiers. |

In templates: `{{ event.antla_tryon_image_url }}`, `{{ event.antla_product_title }}`, and so on.

**Filter out test events.** Filter this trigger on `antla_test_event = false`.

## 2. Metrics: `Antla Campaign Event: <name> [<token>]`

One metric per flow created in the Antla app (Integrations → Klaviyo → Create flow). Older ones are named `Antla campaign event [<token>]`. The 16-character token in the name is the same token that ends the campaign's webhook URL, which is how you match a webhook to the metric it will produce.

Antla sends this event in two situations:
- a shopper completes a try-on that matches the Antla flow's audience, is logged in, is subscribed to marketing and meets Antla's own eligibility checks (Antla checks these; you do not need to re-check them in Klaviyo); or
- something POSTs to the campaign's webhook URL (see `webhook.md`).

Antla creates a matching Klaviyo flow and email template when the Antla flow is set live.

| Property | Notes |
|---|---|
| `antla_original_tryon_image_url` | The try-on the shopper made. **Often `null`**: it is only set when the Antla flow's email type is "Their photo", and it was `null` on every webhook-triggered event we observed. |
| `antla_original_product` | Object for the product that started it (the tried-on product, or the `productId` sent to the webhook). Fields below. |
| `antla_looks` | List of recommended looks, each generated on the shopper's photo. 1 item for "1 recommendation", up to 6 (indexes 0–5) for "Multiple". May be empty for "Their photo". |
| `antla_discount` | `null`, or `{ "code": "…", "percentage": 10 }`. |
| `antla_store_url`, `antla_shop_url`, `antla_about_url`, `antla_news_url`, `antla_contact_url` | Tracked links to the home page, all-products collection, About, News blog and Contact page. |
| `antla_flow_id` | ID of the Antla flow that sent the event. |
| `antla_test_event` | `true` for the sample event Antla sends when the flow is created or tested. Sample events contain `example.com` placeholder data. |

Fields on `antla_original_product` and on each item of `antla_looks`:

| Field | Notes |
|---|---|
| `product_id` | `gid://shopify/Product/…` |
| `product_title` | |
| `product_url` | Storefront URL with Antla's tracking parameters. Use this for every link so Antla can attribute revenue. |
| `product_image_url` | Normal catalog image. |
| `tryon_image_url` | **Looks only.** The generated image of the shopper in this product. |
| `price` | Formatted with currency symbol, e.g. `$200.00`. |
| `price_min`, `price_max` | Numbers. |
| `currency_code`, `currency_symbol` | Taken from Antla's record of the store currency. If prices show the wrong currency, the fix is in Antla/Shopify, not in the template. |
| `product_type`, `vendor` | May be empty. |

In templates: `{{ event.antla_looks.0.tryon_image_url }}`, `{{ event.antla_original_product.product_title }}`, `{{ event.antla_discount.code }}`.

Use the same look index for the image, title, link and price so they describe the same product.

## 3. Profile properties

Antla keeps these up to date on the Klaviyo profile after each try-on. They work in any email, including ordinary campaigns with no Antla trigger, and in segments and flow filters.

| Property | Type | Notes |
|---|---|---|
| `antla_has_tried_on` | boolean | |
| `antla_tryon_count` | number | Lifetime try-ons. |
| `antla_last_tryon_at` | timestamp | |
| `antla_last_tryon_image_url` | URL | Most recent generated image. |
| `antla_last_tryon_product_id` | `gid://shopify/Product/…` | |
| `antla_last_tryon_product_handle` | string | |
| `antla_last_tryon_category` | string | |
| `antla_user_image_url` | URL | The shopper's uploaded photo. Its presence means Antla can generate new looks for this person. Never show it in an email. |
| `antla_tried_on_products` | list of `{id, handle}` | |

In templates, read custom properties with the lookup filter: `{{ person|lookup:'antla_last_tryon_image_url' }}`.

In flow and segment conditions, the property name is written `properties['antla_tryon_count']`.

Don't use the Shopify tag `tried-on-antla` (in the `Shopify Tags` profile property) as a signal in flows, splits or segments. Use the Antla profile properties above instead, e.g. `antla_has_tried_on`.

## 4. Where the product ID lives on common Shopify triggers

A webhook body needs one product ID. These paths were confirmed on real events; still open one recent event for the trigger metric in the target account before relying on a path, because integrations vary.

| Trigger metric | Template path | Value |
|---|---|---|
| Checkout Started (Shopify) | `{{ event.extra.line_items.0.product_id }}` | numeric, first cart line |
| Placed Order (Shopify) | `{{ event.extra.line_items.0.product_id }}` | numeric, first order line (same structure as Checkout Started; confirm on a sample) |
| Ordered Product (Shopify) | `{{ event.ProductID }}` | numeric, fires once per line item |
| Added to Cart (Shopify) | `{{ event.ProductID }}` | numeric string |
| Viewed Product (Klaviyo onsite JS) | `{{ event.ProductID }}` | numeric |
| Customer tried-on an outfit | `{{ event.antla_product_id.id }}` | GID |
| Antla campaign event | `{{ event.antla_original_product.product_id }}` or `{{ event.antla_looks.0.product_id }}` | GID |

Line-item events only expose one product per webhook call. For a cart with several items, `line_items.0` is the first; pick a different index deliberately if needed.

To find the path on an unfamiliar trigger, call `get_events` with `filter: equals(metric_id,"<id>")`, `page_size: 1`, `sort: -datetime`. Shopify checkout and order events are very large, so request only the fields you need (`fields_event: ["event_properties.Items", "event_properties.$extra"]` is still big; narrowing is worth it).

## 5. Template syntax notes

Klaviyo templates use Django-style tags. All of these were rendered successfully with `render_email_template`:

```django
{% if event.antla_discount.code %}Use code {{ event.antla_discount.code }} for {{ event.antla_discount.percentage }}% off.{% endif %}

{% for look in event.antla_looks %}
  {% if look.tryon_image_url %}
    <a href="{{ look.product_url }}"><img src="{{ look.tryon_image_url }}" alt="You wearing the {{ look.product_title }}"></a>
  {% endif %}
{% endfor %}

{{ event.antla_looks|length }}
{{ event.antla_looks|length|pluralize:"look,looks" }}
{% if person.first_name %}{{ person.first_name }}, {% endif %}
{% if event.antla_tryon_count > 1 %}…{% endif %}
{{ person|lookup:'antla_last_tryon_image_url' }}
```

- Event variables are empty outside a flow triggered by the matching Antla metric. A missing variable renders as nothing, so an unguarded `<img src="{{ … }}">` becomes a broken image. Wrap every personal image in `{% if %}`.
- Subject lines and preview text accept the same variables.
- Always include `{% unsubscribe 'Unsubscribe' %}`.
- `default:` only takes a literal. `{{ a|default:event.ProductName }}` makes the whole template fail to render (400); use `{% if a %}{{ a }}{% else %}{{ b }}{% endif %}`.
- Keys with spaces: `{{ event|lookup:'Product Name' }}`.
- "Is the cart item the product they tried on?" works in a template (not in a flow split, which only compares to fixed values). Shopify events carry a numeric ID and Antla stores a GID, so test it as a substring: `{% if person|lookup:'antla_last_tryon_image_url' and event.ProductID|stringformat:"s" in person|lookup:'antla_last_tryon_product_id' %}`. For checkout and order events use `event.extra.line_items.0.product_id|stringformat:"s"`. Rendered true for a match and false for a different product or an empty profile.
