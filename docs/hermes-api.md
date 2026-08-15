# Hermes Public Property API

Set a long random value for `HERMES_API_TOKEN` in the local `.env` file and
restart the Odoo service. For controlled local administration or automated
tests, an Odoo system administrator may instead set
`commercial_property_management.hermes_api_token` in `ir.config_parameter`.
Neither token value belongs in source code.

Every request needs this header:

```text
Authorization: Bearer <HERMES_API_TOKEN>
```

Endpoints:

- `GET /api/hermes/properties?min_area=80&max_rent=2500&availability=available`
- `GET /api/hermes/properties/<property-code>`

Only published, active and available properties are returned. The response is
limited to public name, description, monthly rent, currency, area, type,
features, city and available date. It never includes tenant, lease, internal
note or other private operational data.
