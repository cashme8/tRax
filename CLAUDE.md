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
