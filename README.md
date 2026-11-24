# Antla × Klaviyo skill

A skill for Claude that builds Klaviyo flows, emails and segments with [Antla](https://antla.io) virtual try-on data, through the Klaviyo MCP. Shoppers see **themselves** wearing the product in abandoned cart, browse abandonment, post-purchase, win-back and back-in-stock emails.

It works on any merchant's account: it reads your existing flows, Antla campaigns and brand assets, builds the try-on version of your own flows in draft, checks every path, and finishes with a flow map page of the whole account.

## Install

Download **[antla-klaviyo.zip](https://github.com/Aaron-antla/klaviyo-skill-antla/releases/latest/download/antla-klaviyo.zip)** (always the latest version), then:

| You use | Do this |
|---|---|
| Claude.ai or Claude Desktop | Settings → Capabilities → Skills → upload the zip. Connect Klaviyo, and keep code execution on. |
| Claude Code | Unzip into `~/.claude/skills/` (or a project's `.claude/skills/`) and add the Klaviyo MCP. |
| A Claude Team or Enterprise workspace | An admin can add the zip once for everyone. |

Use the zip above, not GitHub's green "Code → Download ZIP": that one wraps the skill in an extra folder.

Then ask, for example: "Add Antla try-on to my abandoned cart flow" or "Map my Klaviyo flows". Every flow is created in draft; nothing goes live without your say-so.

## What's inside

- `antla-klaviyo/SKILL.md`: how Claude works: look before building, build on your flows, pick the right Antla campaign, verify, hand over, map.
- `antla-klaviyo/references/`: Antla data in Klaviyo, the webhook, tested `create_flow` recipes, the verification pass, the playbook, the flow map.
- `antla-klaviyo/assets/`: email templates and the flow map page design.
- `antla-klaviyo/scripts/`: `verify_flow.py` (checks a flow as Klaviyo stored it) and `build_flow_map.py` (builds the flow map page).
