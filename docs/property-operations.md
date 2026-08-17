# Property Operations and Maintenance

## Purpose

Buildings and commercial units need physical upkeep after they are listed,
reserved or leased: inspections, damage repairs, cleaning, utility issues,
preventive maintenance, and the delivery/return checklist exchanged with a
tenant. Phase 15 adds a **Maintenance** ticket model and a **Delivery/Return
Checklist** model so Property Managers can track and audit this operational
work without exposing it to the public listing API or WhatsApp.

## Maintenance tickets

Open **Commercial Properties → Maintenance** to manage tickets. A ticket
belongs to a building (`Building`) and optionally to one of its commercial
units; leave the unit empty for a building-wide ticket such as a common area
or shared facility.

Each ticket has:

- a **category**: Inspection, Damage, Cleaning, Utilities, Repair, or
  Preventive Maintenance;
- an **assignment** to either an internal owner (a user) or an external
  provider (a contact), never both;
- a **due date** and **cost estimate** / **actual cost**;
- a state machine: `New → Assigned → In Progress → Completed`, with
  `Cancelled` available from any open state.

A ticket can only be assigned once an internal owner or external provider is
set, and can only be completed once completion notes are recorded. Assigning
a ticket to an internal owner schedules a To Do activity for that user. Every
change is tracked in the ticket's chatter for audit history.

Use **Commercial Properties → Maintenance Dashboard** for a pivot view of
ticket volume and estimated cost by category and status.

## Delivery/return checklists

Open **Commercial Properties → Delivery / Return Checklists** to record a
unit handover. Each checklist is a **Delivery** (handing a unit to a tenant)
or **Return** (receiving it back), linked to a commercial unit and optionally
a lease. Add one checklist line per area or item inspected, with a condition
(Good/Fair/Damaged/Missing), notes, and an optional evidence photo. A
checklist can only be completed once it has at least one line; completion
records the acting manager and timestamp.

## Operational status

Commercial units and buildings expose a manager-only **Operational Status**
field:

- **Operational** — no open maintenance ticket and no draft handover.
- **Under Maintenance** — at least one ticket in the Assigned or In Progress
  state (building-wide tickets only affect the building's own status; a
  unit's status only reflects tickets scoped to that unit).
- **Awaiting Handover** — a unit has a draft (incomplete) delivery/return
  checklist.

This field, the ticket list, and the checklist list are all restricted to
**Property Manager**. They are never returned by `get_public_data()` and are
not reachable from the Hermes public API or WhatsApp integration.

## Access

Only Property Managers can read, create, or update maintenance tickets and
delivery/return checklists. Property Users have no menu access to either
model, matching the access level already used for leads, visits,
reservations, and applications.

## Verification

```bash
./scripts/test-module-logic.sh commercial_property_management
npm run test:e2e
```

The module test suite covers the ticket and checklist state machines,
assignment validation, operational status computation, and confirms
`get_public_data()` never includes operational fields. The browser suite
covers manager/Property User access control and a full create → assign →
complete flow for both a maintenance ticket and a delivery checklist.
