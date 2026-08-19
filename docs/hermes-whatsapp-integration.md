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

## Verification

```bash
npm run test:hermes-mcp
npm run test:e2e
```
