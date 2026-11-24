# Verification pass

Run this after creating or changing anything, and before telling the user it is done. It exists because every item on it is a mistake that has actually been made with this integration: flows that were created without error and described to the user as finished, but had paths that sent nothing, links Klaviyo had quietly dropped, and a follow-up that repeated the first email.

The principle: **a successful create call proves nothing about what was built.** Klaviyo validates the shape of a request, not whether the flow does what was intended, and it can store something different from what was sent. So verify what Klaviyo holds, not what you sent, and verify behaviour path by path, not action by action.

Do not report a flow as built, complete or ready until every section below has been done for it. If something can't be checked, say so in the hand-over rather than leaving it out.

## 1. Before creating: design every path to an ending

Write the flow out as a list of paths from the trigger to an end, one line per path, before building the JSON. For each path answer: **what does this shopper receive, and is that deliberate?**

- Every branch of every split needs a decision. "Ends here" is a valid decision only when there is a reason (they converted, another flow owns them). Write the reason down.
- A branch that only sets a profile property, or only calls a webhook, has not sent the shopper anything. If the user asked for an email flow, that path is unfinished.
- **Every webhook path needs a fallback.** Antla drops requests it can't fulfil without telling anyone. After the webhook: wait (30 minutes is plenty; generation takes seconds), check whether the campaign event arrived, and send the normal email if it didn't.
- A follow-up email must differ from the email before it: different template or at least different content. Don't send the same generated image twice.
- Count what you are about to send: number of actions, and number of non-empty links (each `next`, `next_if_true`, `next_if_false`, and each branch's `next` that is not `null`). Keep both numbers.

### Keep the flow a tree

Klaviyo flows are trees. Two paths can share a later step only in one case that has been seen to work: one branch of a split runs an action and then continues into the step its sibling branch goes to directly (for example "yes → webhook → delay" and "no → delay").

Anything else that makes paths converge is unsafe. Branches from different splits pointing at one shared step have produced two different failures: Klaviyo kept one link and **silently set the others to null** (the create call still succeeded), and in another case `create_flow` returned a 500 until the merge was removed.

So when several paths need the same next steps, **give each path its own copy** of the delay, split and email. It is more actions, and it always works.

## 2. After creating: read the flow back and compare

Call `get_flow` with `additional_fields_flow: ["definition"]`. Ask for the whole definition here; this is the one place a full read is worth its size.

Then either run the script or do the same checks by hand.

**With the script** (when you can run Python): save the tool result to a file and run

```bash
python3 scripts/verify_flow.py flow.json --expect-actions <N> --expect-links <N>
```

using the counts from step 1. It prints every path a shopper can take and lists errors (dropped links, unreachable actions, branches to nowhere, emails with no template or subject, a mistyped Antla address, a missing JSON content type, malformed webhook bodies, example values left in) and warnings (webhook with no fallback, an email sent after a webhook with no check that the look arrived, a webhook that is not an Antla address at all, a fixed product ID, repeated email, draft actions inside a live flow). Fix every error. Read every warning and note and decide whether it is intended.

**By hand** (when you can't run it), check all of these against the read-back:

1. The number of actions equals what you sent.
2. The number of non-empty links equals what you sent. If it is lower, Klaviyo dropped links: find which.
3. Starting at `entry_action_id`, follow every link and write out each path to its end. Compare the list with the paths you designed in step 1. Every path must match.
4. Every action is on at least one path.
5. Every email action has a `template_id`, a real subject line, a sender, and preview text.
6. Every webhook action has the right URL (exactly `https://app-antla.com/integrations/klaviyo/webhook/` plus 16 lowercase hex characters, no stray whitespace), a `Content-Type: application/json` header, and a body that is valid JSON with `email` and `productId` (exact spelling), both filled from template variables rather than fixed example values. A fixed `productId` is right only for a single-product send.
7. Every webhook branch is gated on the photo being on file and on nothing else, and between each webhook and any later email on the same path there is a split that checks the look arrived.
8. The trigger metric, trigger filter, flow filter and re-entry setting are what you intended.

The script cannot judge intent. Whichever way you check, read the printed paths as the shopper would experience them and confirm each one is what the user asked for.

## 3. Check the content

- Render every template with `render_email_template` (`fields_template: ["html"]`), at least twice: once with full, realistic data, and once with the optional data missing (no first name, `antla_discount: null`, an empty `antla_looks`, a missing image URL). Read the output. No broken images, no half sentences, no stray punctuation. In the missing-data render a try-on hero simply isn't there; that is correct, because the flow's trigger or split is what guarantees the image exists for real sends.
- Read the rendered HTML for anything that should not reach a shopper: the instruction comment from the asset file, a `__PLACEHOLDER__` left in, a webhook URL.
- Check each template is on a flow whose trigger supplies the variables it uses. `event.antla_looks…` only exists on Antla campaign events; `event.antla_tryon_image_url` only on the try-on metric; `event.extra.line_items…` only on Shopify checkout and order events.
- Check the subject line and preview text render too: they use the same variables and fail the same way.

## 4. Check the webhook

- **Validate the URL against Klaviyo.** Take the 16-character token from the end of the webhook URL and find it in the list of Antla metrics (`Antla Campaign Event: <name> [<token>]`). If no metric contains that token, the URL is wrong or cut short: stop and ask the user to copy it again. A wrong token is accepted by Antla with a 200 and then ignored, so this check is the only thing that catches a bad paste.
- Confirm a live flow is triggered by that metric and contains a live email. Without one, the webhook generates a look and nobody receives it.
- Read that flow's definition for anything that can skip the send after the event has arrived: Smart Sending on the email, flow filters, and the delay before the email (the time gap the merchant set in Antla; tell the user how long it is). A shopper skipped there gets neither the look nor your fallback. Report each one to the user; changing Antla's flow is their decision.
- Confirm the product ID path against one real event for this flow's trigger metric.
- Confirm the webhook is not inside a flow triggered by the same campaign's metric (a loop).
- Know what the campaign generates: read one recent real event on the campaign metric and compare `antla_original_product` with `antla_looks`. If the looks are different products from the original, the campaign's email type is a recommendation, and a shopper who abandoned product A will be shown product B. Tell the user, because for cart and browse recovery they usually expect the same product; the setting is in the Antla app.

## 5. Check the neighbours

- List every live flow on the same trigger metric (`get_flows`, then read the trigger of each candidate, or `get_flows_triggered_by_metric` where available). `get_flows` returns 50 a page; follow `page_cursor` to the end before concluding there is no overlap. Count `manual` flows as well as `live` ones. State each overlap to the user. Two live flows on one trigger means two messages.
- If the new flow shares a trigger with a flow Antla created, one of them must stay in draft.
- Check every gate can actually be passed: for each property a split or filter depends on, look at a few real profiles or events and confirm the value that opens the branch really occurs in this account. A gate nobody can pass looks exactly like a working flow until a real event runs through it.
- Check re-entry: flows on the try-on metric and on Viewed Product need a "not in this flow recently" filter or a re-entry limit.

## 6. After a status change

`update_flow` sets the status of the flow and of **every** action in it. After switching something live or to draft, read the status back and confirm it. When turning a flow live, confirm no action was meant to stay off. When replacing a live flow, switch the old one off first, then the new one on, and confirm both.

## 7. Report honestly

In the hand-over, separate three things:

- **Verified:** what was read back and matched, what was rendered, what was tested.
- **Not verified:** anything that could not be checked from here. An end-to-end run needs the real trigger to fire while the flow is live; say plainly if that has not happened.
- **Decisions for the user:** overlaps with existing flows, the campaign's email type, anything that behaves differently from what they asked for.

A flow that has been read back and matches is "built and checked, not yet run". After a real event has entered, confirm which branch it took; a direct POST to the webhook does not test the flow's splits, because it bypasses them. It is not "working" until a real event has gone through it.
