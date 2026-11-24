# Playbook: what to build with Antla + Klaviyo

Ideas ordered roughly from most to least commonly valuable. Each names the trigger, who it reaches, what Antla supplies, and the recipe or template to start from. Offer the two or three that fit the merchant's situation rather than listing them all.

Ideas 1, 2, 3, 5 and the lookbook series have a built and API-accepted recipe in `flow-recipes.md`. The rest are designs assembled from the same tested building blocks but not yet run end to end, so build them in draft and test before promising results.

The underlying idea is the same every time: a shopper is far more likely to act on a picture of themselves wearing the product than on a catalog photo, so find the moments where a store already emails people about a product and put the shopper in it.

## Recovery

**1. Abandoned checkout, in their own image.**
Checkout Started → split on "can Antla generate for this person" → webhook with the cart's first product. The shopper who left gets an email of themselves in what they nearly bought. Everyone else, and anyone Antla can't produce a look for, gets the usual reminder. Recipe A.

**2. Try-on reminder.**
Tried on, didn't check out, four hours later: send the image they made back to them. This is the highest-intent audience a store has; they have literally seen the product on themselves. Recipe B, `tryon-reminder.html`. If Antla's own "Their photo" flow already covers this, customise that one.

**3. Browse abandonment with a look they never asked for.**
Viewed Product, no add-to-cart, has a photo on file → webhook with the viewed product. They looked at a jacket and an hour later see themselves in it. Shoppers without a photo get `browse-reminder.html`, which invites them to try it on. Recipe C. The surprise is the point, so keep the copy light ("we had to show you").

**4. "You tried on five things and bought none."**
Trigger on the try-on metric filtered to `antla_tryon_count` equals a threshold (so it fires once, not on every later try-on). Send a Multiple-looks campaign via webhook, or a styling-help email. Indecision is a signal that a nudge or an offer may help.

## Growth

**5. Post-purchase: complete the look.**
Three days after an order, send recommendations generated on their photo, chosen to go with what they bought. Buyers Antla can't generate for get `post-purchase-invite.html`. Recipe D. Needs an Antla campaign of type "1 recommendation" or "Multiple".

**6. New arrivals, on you.**
For a product drop: segment "photo on file", and send each of them the new hero product generated on their photo. There is no bulk-generation call; do it with a segment-triggered flow whose only action is the webhook with a fixed `productId` for the new product. The Antla campaign's flow then delivers the email. Throttle with a small segment first: every profile entering is one generation. `verify_flow.py` will warn that the product ID is fixed; here that is intended.

**7. Win-back with a fresh look.**
Trigger from a "lapsed 90 days" segment, split on photo on file, webhook with a current bestseller's product ID. A returning-customer email that shows them something new on themselves.

**8. Back in stock / price drop, personalised.**
Klaviyo's back-in-stock and price-drop triggers carry the product. Add the photo-on-file split and the webhook, with the usual wait, check and fallback. The item they wanted is back, and here they are wearing it.

## Making ordinary email better

**9. The personalised hero in every campaign.**
`assets/profile-hero-block.html` reads profile properties, so it works in normal campaigns with no Antla trigger. Shoppers with a try-on see their latest look as the hero; everyone else sees the standard image with a "See it on you" button that opens the try-on. One block, two audiences, no extra flow.

**10. Invite the people who haven't tried it.**
Segment `antla_has_tried_on` not set. Send a campaign whose buttons link to product pages with `?antla-open-modal=true` appended, which opens the try-on straight away. Every person who tries on becomes reachable by ideas 1–9. Antla-triggered follow-ups need the shopper logged in and subscribed, so encourage sign-in.

**11. Segment by taste.**
`antla_last_tryon_category` and `antla_tried_on_products` show what someone is drawn to before they have bought anything. Use category for campaign targeting ("dress fans get the dress launch first").

**12. Reward the enthusiasts.**
A try-on count threshold → set a profile property (for example `Antla Style Explorer`) → use it for early access or a perk. These shoppers engage far more than average; treat them as a VIP tier.

## Design and copy guidance for try-on emails

- **The generated image is the email.** Put it first, full width, linked to the product. Keep everything else short.
- **Say what it is.** A line such as "generated for you by our virtual try-on" avoids the uncanny moment of seeing oneself in an email unexplained.
- **Speak to one person.** "You in the Isaac Dress" beats "Check out our dresses". Use the product title from the event in the subject line.
- **One product, one button.** For multiple looks, stack them, each with its own title, price and button, all using the same look index.
- **Use the tracked URLs from the event** (`product_url`, `antla_store_url`, …) rather than hard-coded links, so Antla can attribute revenue.
- **Discounts are optional data.** Show the block only when `antla_discount.code` exists. Don't promise a discount in the subject line unless the flow has split on its presence.
- **Don't send the same image twice.** If a follow-up email goes out two days later, change the framing (other looks, the product details, reviews) rather than repeating the hero. `lookbook-followup.html` does this by showing the same products as catalog photos.
- **Use the store's own brand.** The templates ship with a text wordmark and neutral colours. Where Klaviyo holds brand logos and colours for the account, use them.
- **Timing.** Immediately after a try-on is fine when the email is a keepsake of what they made. For recovery, wait: one to four hours after a try-on or checkout, so people who were going to buy anyway aren't interrupted.

## What needs the Antla app (not possible through the Klaviyo MCP)

- Creating a campaign, which is what produces a campaign metric and a webhook URL.
- Choosing the email type (Their photo / 1 recommendation / Multiple), the audience rule, timing, the discount, and whether shoppers are added to a list.
- Sending a test event with realistic data ("Test email" in Antla's flow builder).

When a play needs a campaign that doesn't exist yet, say exactly what to create in Antla (name, email type, audience). Once it exists its metric appears in Klaviyo, and the webhook URL can be built from the token in the metric's name.
