# Financial Operations and Portfolio Performance

## Purpose

Phase 16 gives Property Managers a reliable view of commercial terms,
collection status, vacancy, and unit performance, without adding a hard
dependency on Odoo Accounting. Deposits, rent adjustments, penalties, and
renewals are tracked directly on the lease; occupancy and income are reported
per building.

## Lease deposit

Every lease has a **Deposit Amount** and a **Deposit Status**:
`Pending → Held → Refunded` or `Held → Forfeited`. A deposit can only be
marked **Held** once an amount is set, and can only be **Refunded** or
**Forfeited** from **Held**. The received and resolved dates are recorded
automatically and the status is tracked in the lease chatter.

## Rent adjustments

Open a lease's **Rent Adjustments** tab to record a manager-approved rent
change: effective date, new rent, and a reason. The previous rent is captured
automatically from the lease at creation time. Clicking **Apply** on a draft
adjustment updates the lease's monthly rent, posts an audit message to the
lease chatter, and marks the adjustment **Applied**. An adjustment can only be
applied once, and only while the lease is draft or active.

## Penalties

Open a lease's **Penalties** tab to record a charge (late payment, damage,
contract breach, or other) with an amount greater than zero. A pending
penalty can be marked **Collected** or **Waived**. Use
**Commercial Properties → Penalties** for a cross-lease view of collection
status, with a pivot for delinquency by reason and building.

## Renewals

An active or expired lease can be renewed once from its form (**Renew**
button). This creates a new **draft** lease for the same unit and tenant,
starting the day after the original lease ends, with the same rent and
duration as a starting point. Renewal never activates automatically — a
manager must review and activate it, matching the manager-controlled
activation pattern used for applications since Phase 13. Renewed leases keep
a `Renewed From` / `Renewals` link back to the original lease for audit.

## Portfolio performance

**Commercial Properties → Portfolio Performance** reports, per building:
unit count, occupied/vacant unit counts, occupancy rate, and expected
monthly income (the active lease's rent where one exists, otherwise the
unit's listed rent). Every commercial unit also tracks `Vacancy Days` — the
time since it last became available — visible on the unit form and as an
optional list column.

All of these fields are manager-only and excluded from `get_public_data()`
and the Hermes public API, matching the existing public/private data
boundary.

## Evaluation: Odoo Accounting integration

Odoo Accounting (`account`) was evaluated and deliberately **not** added as a
dependency in this phase. Enabling `account` pulls in chart-of-accounts,
fiscal localization, and journal setup that affects the whole database, not
just this module, and none of it was required to meet the Phase 16
acceptance criteria (identifying vacant, overdue, and high-performing units).
Collection status is tracked natively instead, through `deposit_status` and
`commercial.lease.penalty.state`.

Recommendation for a future phase: if real invoicing, payments, or overdue
reminders are needed, introduce `account` as an **optional** dependency
behind its own module or a config-settings toggle, and generate
`account.move` records from lease/penalty data rather than duplicating
financial fields — do not make core lease management depend on Accounting
being installed.

## Access

Deposit fields, rent adjustments, penalties, renewals, and portfolio metrics
are all restricted to **Property Manager** — the same access level as leases,
leads, visits, reservations, and applications. Property Users have no menu
access to Penalties or Portfolio Performance.

## Verification

```bash
./scripts/test-module-logic.sh commercial_property_management
npm run test:e2e
```

The module test suite covers the deposit, rent adjustment, penalty, and
renewal state machines, and confirms portfolio metrics update when a rent
adjustment is applied. The browser suite covers manager/Property User access
control and a full create → activate → deposit/adjust and
penalty/renew flow for a lease.
