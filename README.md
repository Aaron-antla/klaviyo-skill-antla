# Antla × Klaviyo skill

A skill for Claude that builds Klaviyo flows, emails and segments with [Antla](https://antla.io) virtual try-on data, through the Klaviyo MCP. Shoppers see **themselves** wearing the product in abandoned cart, browse abandonment, post-purchase, win-back and back-in-stock emails.

It works on any merchant's account: it reads your existing flows, Antla campaigns and brand assets, builds the try-on version of your own flows in draft, checks every path, and finishes with a flow map page of the whole account.

## Install

1. Connect the Klaviyo MCP to Claude.
2. Add the `antla-klaviyo` folder as a skill (zip it, or copy it into your skills directory).
3. Ask, for example: "Add Antla try-on to my abandoned cart flow" or "Map my Klaviyo flows".

Nothing goes live without your say-so: every flow is created in draft.

## What's inside

- `antla-klaviyo/SKILL.md`: how Claude works: look before building, build on your flows, pick the right Antla campaign, verify, hand over, map.
- `antla-klaviyo/references/`: Antla data in Klaviyo, the webhook, tested `create_flow` recipes, the verification pass, the playbook, the flow map.
- `antla-klaviyo/assets/`: email templates and the flow map page design.
- `antla-klaviyo/scripts/`: `verify_flow.py` (checks a flow as Klaviyo stored it) and `build_flow_map.py` (builds the flow map page).
