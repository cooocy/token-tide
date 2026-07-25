# Enforce UTC `Z` timestamps and remove manual refresh UI

## Goal

- Ensure every datetime field emitted by the backend response schemas is serialized in UTC with a trailing `Z`.
- Remove manual refresh controls and request paths from the frontend so displayed data relies on backend automatic refreshes.

## Changes

1. Centralize backend datetime serialization and apply it to balance observations, provider refresh metadata, and refresh results.
2. Add deterministic schema tests for naive and offset-aware datetime values.
3. Remove refresh buttons, refresh request state, notifications, and unused refresh API functions/types from the dashboard and provider history pages.
4. Remove refresh-only styling and adjust empty-state copy to describe automatic refreshes.

## Verification

- Review all backend response datetime fields for the shared UTC `Z` serializer.
- Search the frontend for remaining manual refresh controls and calls.
- Run `git diff --check`.
- Leave Python tests and frontend build/type-check commands to the user per repository rules.
