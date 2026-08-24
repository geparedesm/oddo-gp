# Hermes Public Property API

Set a long random value for `HERMES_API_TOKEN` in the local `.env` file and
restart the Odoo service. For controlled local administration or automated
tests, an Odoo system administrator may instead set
`commercial_property_management.hermes_api_token` in `ir.config_parameter`.
Neither token value belongs in source code.

MCP clients also require an independent long random channel credential in
`HERMES_MCP_CHANNEL_TOKEN`, or in the Odoo system parameter
`commercial_property_management.hermes_mcp_channel_token`. This credential
must differ from the bearer token and must not be committed.

Every request needs this header:

```text
Authorization: Bearer <HERMES_API_TOKEN>
```

Endpoints:

- `GET /api/hermes/properties?min_area=80&max_rent=2500&availability=available`
- `GET /api/hermes/properties/<property-code>`
- `POST /api/hermes/properties/<property-code>/enquiries`

Only published, active and available properties are returned. The response is
limited to public name, description, monthly rent, currency, area, type,
features, city and available date. It never includes tenant, lease, internal
note or other private operational data.

The MCP enquiry path may send an authenticated `whatsapp_sender` in place of
`phone`. Odoo accepts that field only when both `X-Hermes-Channel: mcp` and the
constant-time-verified `X-Hermes-MCP-Token` credential are present. The channel
header alone is declarative and grants no trust. Odoo validates and normalizes
the sender, makes it override any mismatched payload phone, and stores it in
both the required contact phone and the manager-only sender audit field.
Ordinary API clients must continue to send `phone`.
