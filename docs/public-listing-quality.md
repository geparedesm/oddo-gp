# Public Listing Quality and Controlled Distribution

## Purpose

Phase 17 improves demand generation for published units while preserving the
public/private data boundary established since Phase 7: a quality checklist,
manager approval audit, publication expiry, unpublish reasons, a lightweight
distribution-channel registry, and campaign attribution for enquiries.

## Quality checklist

Every commercial unit computes a manager-only **Quality Checklist Passed**
indicator, true only when the unit has: a photo, a public name, a public
description, a public monthly rent greater than zero, at least one public
feature, and a **Public Location Description** (a non-sensitive hint such as
"Near the central plaza", never the exact address).

The checklist is informational — a manager can still publish a unit that
does not fully pass it, exactly as before Phase 17. This keeps the existing
`is_published` toggle and every prior phase's public-listing behavior
unchanged; the checklist gives managers a clear signal without silently
blocking publication.

## Publication approval, expiry and unpublish reasons

Publishing a unit (`is_published: True`) automatically records:

- **Publication Date** — the day it was published;
- **Approved By** — the manager who published it.

Unpublishing (`is_published: False`) requires an **Unpublish Reason**
(Manager Decision, Leased, Quality Issue, Expired, Other) in the same write;
attempting to unpublish without one raises a validation error. Re-publishing
clears the previous reason.

Managers can set a **Publication Expiry** date. The daily scheduled action
**Expire Commercial Property Unit Publications** unpublishes any unit past
its expiry date with reason `Expired`, alongside the existing daily lease and
hourly reservation expiry jobs.

## Distribution channels

**Commercial Properties → Distribution Channels** is a manager-only registry
of where units are shared: a website, a property portal, or a social
campaign. A unit can be tagged with the channels it has been shared to. This
phase evaluated and deliberately limited scope to internal tracking — it does
not implement live connectors to external portals or social platforms, which
would require third-party credentials and API integrations outside this
phase's scope. Recording channels here is what makes campaign attribution
(below) possible today, and gives a clear extension point if a specific
connector is approved later.

## Campaign attribution

An enquiry (`commercial.property.lead`) can be attributed to a
**Campaign / Channel**. For WhatsApp/API enquiries, the public
`POST /api/hermes/properties/<code>/enquiries` endpoint and the
`submit_property_enquiry` MCP tool accept an optional `channel` parameter;
if it matches an active distribution channel's name, the lead is attributed
automatically. An unrecognized channel value is silently ignored rather than
rejected, so it cannot be used to enumerate configured channel names.

**Commercial Properties → Campaign Attribution** is a pivot of enquiries by
channel and status, extending the Phase 14 acquisition dashboard with a
channel dimension.

## Access and the public/private boundary

The quality checklist, publication audit fields, expiry date, unpublish
reason/notes, and distribution channels are all manager-only and are never
returned by `get_public_data()`. `get_public_data()` now also returns
`location_hint` alongside the existing public fields. Property Users have no
menu access to Distribution Channels or Campaign Attribution.

## Verification

```bash
./scripts/test-module-logic.sh commercial_property_management
npm run test:e2e
```

The module test suite covers the quality checklist computation, the
publish/unpublish audit and reason requirement, expiry cron behavior, and
channel attribution. The browser suite covers manager/Property User access
control, the full quality-checklist-to-publish-to-unpublish flow, and
attributing an enquiry to a channel.
