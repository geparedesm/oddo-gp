# Lease Operations Dashboard

## Access

The **Operations Dashboard** is available in **Commercial Properties** to users in
**Property Manager**. It opens the active lease pivot view, which provides lease
counts and total monthly rent by status. Property users cannot access lease data
or the dashboard.

The dashboard is available at:

`/web#action=commercial_property_management.action_commercial_lease_operations_dashboard`

Use the **Expiring in 30 Days** and **Expiring in 7 Days** filters to review
active contracts approaching their end dates. The lease list and form also show
**Days to Expiry** for active leases.

## Renewal reminders

The scheduled action **Synchronize Commercial Property Availability** runs daily.
In addition to releasing expired leases, it creates one To Do activity for the
first eligible Property Manager when an active lease is exactly 90, 30, or 7 days
from its end date.

Each activity:

- has the lease end date as its deadline;
- asks the manager to review renewal or closure;
- is deduplicated by lease, reminder threshold, and activity type, so repeated
  cron executions do not create duplicate reminders.

Managers can complete or reschedule reminders from the lease form chatter.

## Languages

English is the module source language. Spanish translations are provided in
`addons/commercial_property_management/i18n/es.po`, including all Phase 9
operations labels, filters, dashboard labels, and expiry activity messages.
After changing translations, update the module to import them:

```bash
./scripts/dev-update-module.sh commercial_property_management
```

## Verification

```bash
./scripts/test-module-logic.sh commercial_property_management
npm run test:e2e
```

The module test suite verifies 90-, 30-, and 7-day activity creation and
idempotency. The browser suite verifies the Commercial Properties workflow.
