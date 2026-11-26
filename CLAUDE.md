# tRax — guidance for Claude Code sessions

tRax is a multi-company web app for Rwandan companies and their accountants: record invoices,
purchases and expenses; calculate RRA taxes (VAT, PAYE, withholding, corporate income tax);
track filing deadlines; prepare returns. Product plan: `tRax — Rwanda Tax Compliance Platform
Product & Tech Plan.docx` in the repo root.

The developer is learning while building: explain key concepts briefly, work in small steps,
and **ask before any decision with real trade-offs**.

## Stack
- Backend: Python 3.12, Django 5, Django REST Framework, PostgreSQL 16 — in `backend/`
- Background jobs: Celery + Redis (`backend/config/celery.py`)
- Frontend: Next.js (App Router, v16) + TypeScript strict + Tailwind + shadcn/ui — in `frontend/`.
  Next 16 differs from older versions: read `frontend/node_modules/next/dist/docs/` before
  writing Next-specific code (see `frontend/AGENTS.md`).
- Local dev: Docker Compose (postgres, redis, backend, worker, frontend)
- Tests: `docker compose run --rm backend pytest`; frontend: `npm run lint` and `npm run typecheck`

## Dependencies
Approved: Django, djangorestframework, djangorestframework-simplejwt, django-environ,
django-cors-headers, psycopg[binary], celery, redis, gunicorn, pytest, pytest-django, pytest-cov,
factory-boy, ruff; Next.js, React, Tailwind, shadcn/ui (and the packages its CLI installs),
@tanstack/react-query, react-hook-form, zod, prettier.
**Ask before adding anything else.**

## Architecture rules (non-negotiable)
- **Modular monolith**: one Django project in `backend/` with apps `accounts`, `companies`,
  `accounting`, `tax_engine`, `compliance`, `documents`, `reports`, `audit`. Create an app only
  when a milestone needs it.
- **Multi-tenant**: every business record has a `company` FK. Every API query is filtered to
  companies the requesting user belongs to via `CompanyMember` (roles: owner, accountant,
  viewer; `is_active`). This filtering lives in a shared base viewset/mixin — never in
  individual endpoints. Records from another company return 404, not 403.
- **Money**: `DecimalField` / `Decimal` only, never float. Currency is RWF. The API serializes
  decimals as strings.
- **Tax rules are data**: `TaxRule(tax_type, rate, effective_from, effective_to, rule_version)`.
  Never hard-code a rate. Seeded rates are marked "to be verified with RRA".
- **The backend computes all official tax amounts.** The frontend only displays them.
- **Tax treatment** on every invoice item, purchase and expense:
  `standard | zero_rated | exempt | non_taxable`.
- **Audit**: creates, updates and deletes of financial records are logged to `AuditLog`
  (user, company, action, entity, timestamp).
- **UUID primary keys** on all our models.
- **Settings from env vars** (django-environ). `.env.example` holds no real secrets.

## Decisions made (Milestone 1)
- Invoice unit prices are **VAT-exclusive**; the server adds VAT.
- VAT rounding: **per line, ROUND_HALF_UP to whole RWF**; invoice VAT = sum of line VAT.
  (To be confirmed with RRA.)
- Standard-rated expenses count toward input VAT, like purchases.
- Inviting a member = adding an existing user by email (email invitations later).
- Roles: all roles read; owner + accountant create/edit records, company and tax profile;
  only owners manage members. A company must keep at least one active owner.
- Tenant scoping lives in `backend/companies/scoping.py`: business-record viewsets subclass
  `CompanyScopedViewSet`; company-settings views use `CompanyFromUrlMixin`.
- TaxProfile is history (new row per change, never edited); `company.tax_profile_on(date)`.
- Members and companies are deactivated, never deleted.
- Business-record models subclass `companies.models.CompanyOwnedModel`; links to other records
  use `CompanyScopedPrimaryKeyRelatedField` so only same-company ids are accepted.
- Line VAT lives in `tax_engine/vat.py` (`vat_for_line`); `accounting/pricing.py` applies it.
  Computed money fields are `editable=False` (read-only in the API). Each priced line stores
  the `tax_rule` it used.
- A company that isn't VAT-registered on the issue date charges 0 VAT on sales.
- Invoice lifecycle: draft (editable, deletable) → issued (locked; counts for VAT; payable)
  → cancelled (only if unpaid). Status changes only via `/issue/` and `/cancel/`.
  Issuing re-prices with the rules in force. Payments can't exceed the balance.
- `Supplier.vat_registered` (default True): unregistered suppliers' purchases/expenses carry
  0 input VAT.
- `tax_engine.services.calculate_vat(company, start, end)`: issued invoices only; input VAT
  claimable only on dates the company is VAT-registered. Records without a supplier EBM
  receipt are **counted with a warning** for now (TODO(EBM): make strict). Warnings have a
  stable `code` the frontend can use.
- Audit: `CompanyContextMixin` (base of every company view) logs create/update/delete via
  `audit.mixins.AuditedMixin`, storing `{field: [old, new]}`. Custom actions (issue, cancel)
  use `audited_action`. New views must save through `perform_create/update/destroy` or the
  `audited_*` helpers — never `instance.save()` directly in a view. Models can add related
  data to the log with `audit_snapshot_extra()` (Invoice adds its lines). AuditLog is
  append-only. Django admin edits are NOT in AuditLog (admin keeps its own history).
- Frontend conventions (`frontend/src`):
  - `lib/api/types.ts` mirrors the DRF serializers — update it when a serializer changes.
    Money/rates are strings end to end; `lib/format.ts` formats them without `Number()`.
  - `lib/api/client.ts` is the only `fetch` caller (Bearer token, refresh-on-401, DRF errors →
    `ApiError.fieldErrors` with paths like `items.0.quantity`).
  - Company-scoped endpoint functions take `companyId` first (sent as X-Company-ID) and every
    query key includes `company.id`. Don't read the company from global state in API calls.
  - Logged-in pages are client components under `app/(app)/` wrapped by `AppShell`;
    `experimental.instantInsights.validationLevel = "manual-warning"` because they can't
    render on the server (token lives in the browser).
  - Forms: react-hook-form + zod via our own `zodResolver` in `lib/forms.ts` (no
    @hookform/resolvers). Native `<select>` (`components/ui/native-select.tsx`).
  - Forms never compute VAT or totals; they show the server's numbers after saving.
- `backend/tests/test_every_endpoint_is_scoped.py` fails if any `/api/` view isn't built on
  `CompanyContextMixin` or listed (with a reason) in its `ALLOWED_UNSCOPED`. Don't add to the
  allowlist without a real reason. `tests/test_tenant_isolation.py` is the A-vs-B acceptance
  test: extend it when adding a new company-owned record type.
- Booleans with tax consequences use `common.serializers.ExplicitBooleanField` (DRF otherwise
  reads a flag omitted from an HTML-form POST as False).
- Tests use the `vat_18` fixture (root conftest) instead of relying on seed data.
- Active company is sent by the frontend in the `X-Company-ID` header.
- JWT: access token in memory, refresh token in localStorage.
  TODO before production: move refresh token to an httpOnly cookie.

## Not yet (leave TODO notes where they plug in)
EBM/VSDC integration, RRA e-Tax filing, payroll (PAYE + RSSB), SMS (Africa's Talking),
mobile money (MTN MoMo / Airtel Money), two-factor auth.

## Working style
After each step: run the tests, then report what was done and what's next.
Never run `git commit` or `git push`: the developer commits. At the end of each step, write a
commit message for them to use.
