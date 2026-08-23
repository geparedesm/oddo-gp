# Hermes WhatsApp property search

This project exposes the Odoo public property API to Hermes through a local MCP
server. The MCP server has no Odoo database access: it calls only the bearer
token-protected public endpoints and therefore can return only the public
property contract.

## Prerequisites

- The Odoo service is running locally.
- `HERMES_API_TOKEN` is set in the project `.env`, or
  `commercial_property_management.hermes_api_token` is set in Odoo system
  parameters; do not put the token in a Hermes configuration file or commit it.
- Hermes Gateway is configured with WhatsApp and running.

## Install the MCP server

From the project root, register the local stdio server once:

```bash
hermes mcp add odoo-properties --command bash --args /home/gp/odoo-gp/scripts/run-hermes-property-mcp.sh
hermes mcp test odoo-properties
hermes gateway restart
```

The launcher loads the project `.env` only into the MCP subprocess and falls
back to the Odoo system parameter when needed. Hermes therefore does not need a
copy of `HERMES_API_TOKEN` in its configuration. After the gateway restarts,
Hermes makes the tools available to WhatsApp conversations as:

- `mcp_odoo_properties_search_properties`
- `mcp_odoo_properties_get_available_properties`
- `mcp_odoo_properties_get_property`
- `mcp_odoo_properties_get_property_photo`

## Conversation behavior

For a generic availability question ("do you have anything available?"), call
`search_properties` with no filters and lead the reply by asking for a human
location reference — street, zone, nearby landmark or building name — per the
policy in `docs/whatsapp-lead-intake.md`. Never proactively ask for a budget
or a minimum area.

Use `get_available_properties` only when the prospect volunteers a budget or
area on their own. Map "up to 1200 per month" to `max_monthly_rent=1200`, and
"at least 100 square meters" to `minimum_area=100`. Use `get_property` only
with a code returned by a previous property search.

The tools return the API payload unchanged. They do not expose internal names,
tenants, leases, deposits, or operational notes. An empty result is a valid
response and should be reported as no matching published available properties.
Invalid filters are returned as API validation errors.

When `get_property` returns a unit with a `photo_url`, the MCP server
downloads the photo from the authenticated binary route
(`/api/hermes/properties/<code>/photo`) and delivers it as a native MCP
ImageContent block alongside the JSON text, instead of just returning the
relative URL. Hermes converts that block into a `MEDIA:<path>` reference and
the WhatsApp gateway sends it as a native image attachment. If the unit has no
photo, `photo_url` is `null` and no image is fetched or attached. The
`virtual_tour_url` digital-visit link is always shared as plain text — it is
never fetched or attached as media.

### Refreshing details and photos instead of answering from history

A unit's availability, price, or photo can change between messages in the
same WhatsApp conversation (a manager can add or update a photo at any time).
`search_properties` and `get_property` therefore instruct the model to always
call the tool again for a fresh answer whenever the prospect asks about
availability, unit details, or photos — even when the conversation history
already contains an earlier answer about the same unit. The model must never
infer photo availability, price, or availability status purely from history.

For a photo question specifically ("¿Tiene foto?", "¿me la puedes mostrar?"),
call the dedicated `get_property_photo` tool with the unit's `property_code`.
It always re-queries `getProperty` first to validate the current record, then
only downloads and attaches the photo if the current record has a
`photo_url`; if it does not, it returns the current property details as text
only, without inventing or assuming a photo exists. This applies even if
`get_property` was already called earlier in the same conversation.

## Verification

```bash
npm run test:hermes-mcp
npm run test:e2e
```
