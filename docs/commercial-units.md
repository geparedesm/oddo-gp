# Commercial Units

## Purpose

A `Commercial Property` represents a building or shared address. A `Commercial Unit` is the independently rentable local inside that building. Every lease, public listing and availability state belongs to a unit.

## Manager workflow

1. Open **Commercial Properties → Properties** and create/select the building.
2. Open the **Commercial Units** tab, then add a unit for every rentable local.
3. Give each unit a clear human-facing name, such as `Ground floor corner unit` or `Local next to the pharmacy`; add area, rent, facade description and public listing details.
4. Create contracts from **Lease Contracts**, selecting both the building and the commercial unit.
5. A confirmed lease changes only its unit to Reserved/Rented. Other units in the building remain independently available.

## Upgrade behavior

During module update, every legacy one-property/one-local record receives one default commercial unit. It keeps the previous public reference so existing Hermes property links keep resolving. Existing leases are assigned to that default unit.

## Access and public API

Property Users can read units but cannot create or edit them. Property Managers manage units and lease history. The Hermes API returns only published, available units and includes the building name, city, public unit description, area, rent and public features. It never returns lease, tenant, notes or manager-only data.
