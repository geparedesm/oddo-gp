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

- [ ] Create the `commercial.property` model with identity, address, dimensions,
      rent, availability date, status, notes and active fields.
- [ ] Add statuses: Available, Reserved, Rented, Maintenance and Inactive.
- [ ] Add model access rights and record rules.
- [ ] Add list, form and search views.
- [ ] Add sequence-generated property codes.

Done when: a Manager can create, edit, archive and search a property; a User
can only perform the intended read-only actions.

## Phase 3 - Property Workflow and Usability

Goal: make inventory status easy to understand and operate.

- [ ] Add a Kanban view with status, area and monthly rent.
- [ ] Add saved filters for Available, Rented and Maintenance.
- [ ] Add photos and internal notes.
- [ ] Improve field help, validation messages and form layout.

Done when: a user can identify available properties from the menu, search and
Kanban views without opening every record.

## Phase 4 - Tenants

Goal: manage tenants using Odoo contacts.

- [ ] Extend `res.partner` with tenant fields such as tenant flag,
      identification number and internal notes.
- [ ] Add a Tenants menu and filtered contact action.
- [ ] Support both people and companies.
- [ ] Restrict private tenant information to authorized roles.

Done when: a Manager can create a tenant and open the tenant from the Commercial
Properties menu.

## Phase 5 - Lease Contracts

Goal: record the contract history between a property and a tenant.

- [ ] Create the `commercial.lease` model.
- [ ] Add draft, active, expired and cancelled states.
- [ ] Link lease, property and tenant records.
- [ ] Enforce at most one active lease per property.
- [ ] Show lease history on the property form.

Done when: a Manager can create and activate a lease, and the property shows
the current tenant and previous leases.

## Phase 6 - Availability Automation

Goal: make property availability depend on lease data instead of manual input.

- [ ] Set a property to Rented when its current lease becomes active.
- [ ] Set a property to Reserved for a future confirmed lease.
- [ ] Set a property to Available when the current lease ends or is cancelled.
- [ ] Add automated tests for each state transition and invalid overlap.

Done when: changing a lease updates the property status correctly without a
manual property edit.

## Phase 7 - Public Property Layer and Hermes API

Goal: expose only safe available-property data to an external agent.

- [ ] Add public name, description, price, features and publication fields.
- [ ] Create a separate public-data serializer or model method.
- [ ] Add authenticated endpoints for property search and property detail.
- [ ] Add filters for availability, minimum area and maximum rent.
- [ ] Test that tenant data, deposits, internal notes and contracts are never
      returned by the API.

Done when: a valid API client can search published available properties, while
unauthorized clients and private fields are rejected.

## Phase 8 - Hermes and WhatsApp Integration

Goal: connect the stable public API to conversational property search.

- [ ] Define `search_properties`, `get_property` and
      `get_available_properties` tools for Hermes.
- [ ] Convert conversational budget and area requests into API filters.
- [ ] Test successful, empty-result and invalid-request conversations.

Done when: a WhatsApp conversation can return only the intended public property
information from Odoo.

## Phase 9 - Operations and Release Quality

Goal: provide operational visibility after the core workflow is stable.

- [ ] Add dashboard metrics and upcoming-expiry indicators.
- [ ] Add lease-expiry activities at 90, 30 and 7 days.
- [ ] Complete Spanish and English translations.
- [ ] Run module-upgrade, security review, UX review and Playwright E2E tests.
- [ ] Document the administrator and developer workflows.

Done when: all targeted checks pass and the application can be handed to an
administrator with a clear setup and usage guide.
