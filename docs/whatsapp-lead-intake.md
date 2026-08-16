# WhatsApp Lead Intake

Hermes may only create a non-binding enquiry after the prospect explicitly consents. It collects name, phone, selected published available unit, optional message and visit request. It does not create tenants, reservations or leases. Property Managers alone can access Enquiries and must review the automatically scheduled activity.

## Operating policy

- A WhatsApp enquiry, visit request or manager-created tenant draft is not a reservation, quotation acceptance or lease. Availability and price remain subject to manager review and a signed contract.
- Hermes must first identify the published available unit using a human reference such as street, zone, nearby business, building name, public photos or facade description. It must not require a QR code, live location or technical property code.
- Before asking for contact details, Hermes states the purpose of collection and obtains explicit consent. It submits only the fields accepted by the endpoint.
- Property Managers review new enquiries through the scheduled activity, qualify or reject them, and alone may create a tenant draft. Creating a tenant draft does not create a reservation or lease.
- Ecuador defaults: active enquiries are anonymized after 180 days; rejected enquiries after 30 days. The consent audit fields retain policy version, purpose and timestamp for 730 days. The nightly anonymization job clears contact data, desired start date, message and visit request once a retention deadline is reached.
- The first human response SLA is 8 business hours. A WhatsApp lead receives a manager review activity due the next business day. Visits are offered Monday to Saturday, from 09:00 to 18:00, and require manager confirmation.
- The endpoint is disabled by default. A system administrator must explicitly enable it in Commercial Properties → WhatsApp Policy after approving the current Ecuador policy version.

The public endpoint is bearer-token authenticated and accepts only `POST /api/hermes/properties/<unit-code>/enquiries`. It accepts an explicit boolean consent, contact name and phone, plus optional contact and visit fields. It returns only a neutral receipt and never exposes lead, tenant, lease or internal data.
