# Commercial Property Management - Development Roadmap

Build a new Odoo 16 Community module from scratch in small, verifiable stages.
Complete and test one phase before starting the next. Do not reuse the previous
compiled module or its database state.

## Working Rules

- Keep the technical module name: `commercial_property_management`.
- Use a clean development database for the new module. Do not delete the current
  database or its data without a confirmed backup and explicit approval.
- At the end of every phase: upgrade the module, inspect Odoo and Docker logs,
  run the relevant automated checks, and test the listed browser flow.
- Before closing a phase, run `npm run test:all`. It installs the module in an
  isolated temporary database, upgrades it in the development database, and
  runs the browser smoke test. The temporary database is removed after success
  and retained after a failure for diagnosis.
- Add security and translation-ready strings with each feature, not as a final
  cleanup task.

## Phase 0 - Clean Start

Goal: create an isolated baseline with no dependency on the previous module.

- [x] Choose and create a clean local Odoo development database.
- [x] Confirm the old compiled module is absent; no archive or deletion was
      required.
- [x] Create a fresh `commercial_property_management` module directory.
- [x] Confirm the Docker services and Playwright smoke test can run.

Done when: the new database is available and the repository contains no source
files copied from the previous module.

## Phase 1 - Module Skeleton and Access

Goal: install an empty but correctly structured module.

- [x] Add the manifest, Python package, security directory, data directory and
      views directory.
- [x] Add minimal dependencies: `base`, `contacts` and `mail`.
- [x] Create User, Manager and Administrator security groups.
- [x] Add the root Commercial Properties menu, visible only to authorized users.
- [x] Add a basic module icon and translatable labels.

Done when: the module appears in Apps, installs and upgrades without errors,
and its root menu is visible to an Administrator.

## Phase 2 - Property Inventory

Goal: register and manage commercial properties.

- [x] Create the `commercial.property` model with identity, address, dimensions,
      rent, availability date, status, notes and active fields.
- [x] Add statuses: Available, Reserved, Rented, Maintenance and Inactive.
- [x] Add model access rights and record rules.
- [x] Add list, form and search views.
- [x] Add sequence-generated property codes.

Done when: a Manager can create, edit, archive and search a property; a User
can only perform the intended read-only actions.

## Phase 3 - Property Workflow and Usability

Goal: make inventory status easy to understand and operate.

- [x] Add a Kanban view with status, area and monthly rent.
- [x] Add saved filters for Available, Rented and Maintenance.
- [x] Add photos and internal notes.
- [x] Improve field help, validation messages and form layout.

Done when: a user can identify available properties from the menu, search and
Kanban views without opening every record.

## Phase 4 - Tenants

Goal: manage tenants using Odoo contacts.

- [x] Extend `res.partner` with tenant fields such as tenant flag,
      identification number and internal notes.
- [x] Add a Tenants menu and filtered contact action.
- [x] Support both people and companies.
- [x] Restrict private tenant information to authorized roles.

Done when: a Manager can create a tenant and open the tenant from the Commercial
Properties menu.

## Phase 5 - Lease Contracts

Goal: record the contract history between a property and a tenant.

- [x] Create the `commercial.lease` model.
- [x] Add draft, active, expired and cancelled states.
- [x] Link lease, property and tenant records.
- [x] Enforce at most one active lease per property.
- [x] Show lease history on the property form.

Done when: a Manager can create and activate a lease, and the property shows
the current tenant and previous leases.

## Phase 6 - Availability Automation

Goal: make property availability depend on lease data instead of manual input.

- [x] Set a property to Rented when its current lease becomes active.
- [x] Set a property to Reserved for a future confirmed lease.
- [x] Set a property to Available when the current lease ends or is cancelled.
- [x] Add automated tests for each state transition and invalid overlap.

Done when: changing a lease updates the property status correctly without a
manual property edit.

## Phase 7 - Public Property Layer and Hermes API

Goal: expose only safe available-property data to an external agent.

- [x] Add public name, description, price, features and publication fields.
- [x] Create a separate public-data serializer or model method.
- [x] Add authenticated endpoints for property search and property detail.
- [x] Add filters for availability, minimum area and maximum rent.
- [x] Test that tenant data, deposits, internal notes and contracts are never
      returned by the API.

Done when: a valid API client can search published available properties, while
unauthorized clients and private fields are rejected.

## Phase 8 - Hermes and WhatsApp Integration

Goal: connect the stable public API to conversational property search.

- [x] Define `search_properties`, `get_property` and
      `get_available_properties` tools for Hermes.
- [x] Convert conversational budget and area requests into API filters.
- [x] Test successful, empty-result and invalid-request conversations.

Done when: a WhatsApp conversation can return only the intended public property
information from Odoo.

## Phase 9 - Operations and Release Quality

Goal: provide operational visibility after the core workflow is stable.

- [x] Add dashboard metrics and upcoming-expiry indicators.
- [x] Add lease-expiry activities at 90, 30 and 7 days.
- [x] Complete Spanish and English translations.
- [x] Run module-upgrade, security review, UX review and Playwright E2E tests.
- [x] Document the administrator and developer workflows.

Done when: all targeted checks pass and the application can be handed to an
administrator with a clear setup and usage guide.

## Phase 10 - Multi-unit Property Structure

Goal: represent one building with multiple independently rentable commercial units.

- [x] Add a building/property parent and commercial-unit child structure.
- [x] Move unit-level availability, rent, photos, public details and lease history
      to each commercial unit.
- [x] Preserve existing one-property/one-unit records through an explicit
      migration path.
- [x] Verify that leasing one unit never changes the availability of other units
      in the same building.

Done when: Managers can lease and publish individual units within one building.

## Phase 11 - WhatsApp Lead Intake and Visit Requests

Goal: turn an enquiry from a public sign into a consented, manager-reviewed lead.

- [x] Add a manager-only lead pipeline with consent, contact details, desired
      start date, visit request and follow-up activities.
- [x] Let Hermes identify a building/unit through street, zone, public photos and
      human-facing descriptions, without requiring QR codes, live location or
      technical codes.
- [x] Add a narrow authenticated lead-submission API and MCP tool.
- [x] Ensure chat never creates a tenant, reservation or lease automatically.

Done when: A WhatsApp enquiry creates a safe lead and visit request for the
correct commercial unit.

## Phase 12 - Qualification, Visits and Controlled Reservations

Goal: convert reviewed leads into appointments and manager-approved reservations.

- [x] Add visit requests, scheduling, assignment, confirmation and cancellation.
- [x] Add time-limited reservation requests with manager approval and expiry.
- [x] Prevent conflicts with active leases, future leases and other reservations.
- [x] Add activities for visit follow-up and reservation expiry.

Done when: A manager can approve a non-conflicting, time-limited reservation
without granting it automatically through WhatsApp.

## Phase 13 - Applications, Documents and Contract Handoff

Goal: prepare a reviewed prospect for a manager-controlled commercial lease.

- [x] Add application checklists and approval states for people and companies.
- [x] Use a secure authenticated upload flow for documents; never collect them in
      WhatsApp.
- [x] Generate non-binding proposals from manager-approved terms.
- [x] Create only draft leases from approved applications; keep final activation
      under manager control.

Done when: Every active lease is traceable to an approved application and manual
manager decision.

## Phase 14 - Acquisition Analytics and Operational Hardening

Goal: measure conversion while protecting the public automation channel.

- [x] Measure enquiry, response, visit, reservation, contract and lost-reason
      conversion by building and unit.
- [x] Add rate limits, idempotency, abuse detection and retention/anonymization
      for public leads.
- [x] Restrict WhatsApp automation to safe lead-intake capabilities.
- [x] Add alerts for API, MCP and queue failures.

Done when: Managers can measure demand and the public channel is monitored and
privacy-compliant.

## Phase 15 - Property Operations and Maintenance

Goal: manage inspections, incidents, repairs and handover work per unit.

- [x] Add maintenance tickets, categories, assignment, costs and audit history.
- [x] Add delivery/return checklists with manager-only evidence and photos.
- [x] Show operational status and maintenance history on buildings and units.

Done when: Managers can manage maintenance without exposing operational data in
public listings or WhatsApp.

## Phase 16 - Financial Operations and Portfolio Performance

Goal: monitor commercial terms, collection status, vacancy and unit performance.

- [x] Add manager-controlled deposits, rent adjustments, penalties and renewals.
- [x] Evaluate Odoo Accounting integration for invoices, payments and overdue
      reminders.
- [x] Add occupancy, vacancy, income, delinquency and renewal reporting.

Done when: Authorized managers can identify vacant, overdue and high-performing
units from Odoo.

## Phase 17 - Public Listing Quality and Controlled Distribution

Goal: improve demand generation while preserving the public/private data boundary.

- [x] Add public-listing quality checks for unit photos, name, area, rent,
      features and non-sensitive location descriptions.
- [x] Add manager approval, publication expiry and unpublishing reasons.
- [x] Evaluate controlled distribution to a website, property portals and social
      campaigns.
- [x] Attribute enquiries and conversions to buildings, units and campaigns.

Done when: Only approved available units are distributed publicly and managers
can measure their conversion performance.

## Phase 18 - Conversational Discipline, Budget Capture and Rich Unit Replies

Goal: keep a WhatsApp conversation focused on one unit at a time, capture buyer
intent, and present each unit with a photo, visit options and a USD price.

- [ ] Stop Hermes from listing or suggesting other available units once a
      prospect is discussing a specific unit; only call `search_properties`
      again if the prospect explicitly asks for alternatives or the unit they
      were discussing becomes unavailable.
- [ ] Before searching or presenting a unit, have Hermes ask the prospect's
      desired zone/location if not already given. Add a matching `zone`/
      `location` filter to `search_public_units` and the
      `/api/hermes/properties` endpoint (soft match against
      `public_location_hint`/`city`, not an exact match).
- [ ] Always ask the prospect's budget before or while presenting a unit, and
      store it on `commercial.property.lead` as a new `budget` field, passed
      through the `submit_enquiry` payload, so Managers can compare stated
      willingness-to-pay against each unit's `public_monthly_rent`.
- [ ] Add a manager-set `virtual_tour_url` field to `commercial.property.unit`
      (part of the publication quality checklist) and include it in
      `get_public_data()`.
- [ ] Add an authenticated photo endpoint (e.g.
      `/api/hermes/properties/<code>/photo`) so Hermes/WhatsApp can fetch and
      attach the unit's `image_1920` as media; a bare link will not render
      inline in WhatsApp.
- [ ] Make every unit reply from Hermes include: the photo (via the new
      endpoint), the virtual tour link, and an explicit offer to request a
      physical visit (reusing the existing `visit_requested` flag already
      accepted by `submit_enquiry`).
- [ ] Convert `public_monthly_rent` to USD in `get_public_data()` using
      `res.currency` conversion rates, instead of returning the company's
      operating currency. Keep internal records (leases, rent, deposits)
      unchanged in their current currency.
- [ ] Make the public currency a setting, not a hardcoded conversion. Add a
  `res.config.settings` field (default USD) next to the other Hermes settings
  instead of hardcoding USD in the controller, so a future market change
  doesn't require a code change.
- [ ] Verify `res.currency` exchange rates are actually kept fresh (a rate-update
  cron or manual rate entry). A stale EUR->USD rate will misquote every price
  Hermes sends; this becomes more visible now than before since managers
  never saw the converted number.
- [ ] Treat the zone/location filter as soft matching (`ilike`), not exact —
  prospects phrase areas loosely. If it returns zero units, have Hermes ask
  for a different area instead of a dead end.
- [ ] Store the new `budget` field in USD, matching the now-USD
  `public_monthly_rent`, so Phase 16's demand/price reporting can compare them
  directly without a conversion step.
- [ ] "Never mention other units" is a Hermes tool-use/system-prompt rule, not
  just a backend change — also double check `get_public_data()` never leaks a
  sibling-unit hint (e.g. a "similar units" field) that would undercut it.
- [ ] Reuse the same bearer-token check (`_is_authenticated`) on the new photo
  endpoint. Consider serving a resized copy rather than the manager-facing
  full-resolution `image_1920` to limit bandwidth and avoid exposing the
  original asset.
- [ ] Update Hermes's tool descriptions (from Phase 8) to document the new `zone`
  filter and the USD currency, so the AI's behavior matches the backend
  change immediately rather than drifting from stale tool docs.
Done when: A WhatsApp prospect is asked for zone and budget, sees prices in
USD, receives a photo and virtual-tour link with every unit reply, is offered
a physical visit, and is never shown other units unless they ask.




