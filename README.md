# InternTrack

**Internship Placement and Monitoring System** — a final-year HND project built for the Department of Software and Web Development, School of Computing, Federal Polytechnic Offa.

InternTrack manages the full lifecycle of student industrial attachment: supervisors post vacancies, coordinators approve them, students apply, coordinators place students with supervisors, and supervisors track daily logbooks and formal assessments through to completion.

---

## Table of contents

1. [Tech stack](#tech-stack)
2. [User roles](#user-roles)
3. [Project structure](#project-structure)
4. [Core workflows](#core-workflows)
5. [Key design decisions](#key-design-decisions)
6. [Setup](#setup)
7. [Known limitations / in progress](#known-limitations--in-progress)
8. [Notes for future development](#notes-for-future-development)

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Django 4.2, Python 3.13 |
| Database | SQLite (development) |
| Frontend | Bootstrap 5.3, Bootstrap Icons, vanilla JavaScript |
| Charts | Chart.js |
| Deployment target | Render.com |

No JavaScript framework, no REST API layer — this is a traditional server-rendered Django project. Every page is a Django template; interactivity (role-conditional form fields, live theming, notification polling) is plain `fetch()`/DOM JavaScript, no build step required.

---

## User roles

InternTrack has exactly four roles. Admin is **not** stored as a role value — it's derived purely from Django's built-in `is_superuser` / `is_staff` flags, and always takes priority over whatever `role` happens to say.

| Role | Manages | Scoped to |
|---|---|---|
| **Admin** | Whole system | Everything — system-wide visibility |
| **Coordinator** | One department | Their own department's students, placements, applications |
| **Supervisor** | One company, one department | Students they're actively supervising |
| **Student** | Their own placement | Their own department's approved placements only |

A coordinator or supervisor is locked to exactly **one** department each — this is enforced at three levels (form, model, and database query) and is the backbone of almost every permission check in the system. See [Key design decisions](#key-design-decisions) below.

---

## Project structure

| App | Responsibility |
|---|---|
| `accounts` | Custom user model (all four roles live on one `CustomUser` table), registration, login, dashboards, profile |
| `placements` | Placement postings, the supervisor submission → coordinator approval workflow, student applications |
| `logbook` | Daily logbook entries, weekly reports, supervisor/coordinator review |
| `assessment` | Mid-term and final assessments, criteria-based scoring, grade calculation |
| `announcements` | Coordinator broadcasts to students/supervisors, scoped by department and affiliation |
| `reports` | Individual and aggregate PDF/CSV exports for coordinators |
| `notifications` | In-browser notification bell — polling-based, **in progress, not yet fully wired up** (see [Known limitations](#known-limitations--in-progress)) |

---

## Core workflows

### 1. Placement lifecycle

```
Supervisor submits vacancy
        │
        ▼
   status: pending
   (invisible to students)
        │
        ▼
Coordinator (matching department) reviews
        │
   ┌────┴────┐
   ▼         ▼
Approved   Rejected
   │
   ▼
Visible to students in that
exact department only
```

**Coordinators can no longer create placements directly.** Every placement must originate from a supervisor's own submission. This is a deliberate design decision made mid-project: when coordinators could post placements by hand, nothing stopped a placement being paired with the wrong company or an unrelated supervisor. Since a supervisor's account already carries their real `company_name` and one locked `supervisor_department`, every placement they submit is correctly paired by construction — there's no dropdown for a human to get wrong.

Once approved, `posted_by` and `created_by` are set to the approving coordinator, and the placement behaves exactly like anything a coordinator manages directly — it appears in their "Manage Placements" list, their reports, their stats.

A coordinator can still edit a placement's operational details afterward (title, description, dates, slots) — but `company_name` and `assigned_supervisor` are **permanently locked** once set, for the same reason above.

### 2. Application lifecycle

- A student sees only placements matching their **exact** department (no "All Departments" wildcard — that option was deliberately removed system-wide).
- A student can apply to multiple placements at once.
- The moment a coordinator **accepts** one application:
  - That application → `accepted`
  - Every other **pending** application from that same student → automatically `rejected`, with the note *"Auto-closed — placed at [Company Name]"*
  - A supervisor must be assigned before acceptance is allowed — the form will not submit without one.
- The supervisor dropdown, when accepting, is either locked to the placement's `assigned_supervisor` (the normal case, since every placement now has one from creation) or filtered to supervisors whose registered company name matches (a fallback path, mostly relevant to legacy data from before this workflow existed).
- Once accepted, a student cannot apply to any further placements.

### 3. Logbook lifecycle

- A placed student submits one entry per day: activities, hours, optional attachment.
- The assigned supervisor approves or rejects each entry, with a required comment on rejection.
- **Coordinator fallback**: if a placement's supervisor is unavailable, slow, or otherwise can't respond, the coordinator who owns that placement can step in and review the entry directly — same approve/reject form, same validation rules. This exists so a pending log entry is never permanently stuck with no one able to act on it.

### 4. Assessment lifecycle

- Two assessments per student per placement: **mid-term** and **final**.
- Scoring is criteria-based — each `AssessmentCriteria` row has its own configurable `max_score` (not a fixed 10-point scale), covering both soft skills and technical skills categories.
- A supervisor must score every active criterion before submitting — partial submissions are rejected.
- `total_score` and `max_possible` are recalculated and cached on the `Assessment` row itself each time scores are saved, so percentage/grade lookups don't need to re-sum every time.
- Grade letters (A–F) are derived from percentage thresholds (70/60/50/45).
- A student can acknowledge a submitted assessment (a simple read receipt, timestamped).

### 5. Announcement lifecycle

A coordinator can broadcast to:
- **Everyone** / **Students only** — scoped strictly to students in the coordinator's own department, never system-wide.
- **All supervisors** — scoped to supervisors who are actually affiliated with that coordinator (i.e., supervising at least one accepted student under one of that coordinator's placements), never every supervisor in the system.
- **A specific department**, **specific student**, or **specific supervisor**.

The department field on the announcement form is locked to the coordinator's own department, the same locking pattern used on placement creation.

### 6. Reports

Coordinators can generate, per student or aggregated across their whole department:
- An on-screen HTML report
- A print/PDF version (same data, same computation — the two views share one context-building function so they can never silently disagree)
- A CSV export

The aggregate report also surfaces a **"Missing Supervisor"** count, so a coordinator can spot at a glance if any placed student somehow lacks a supervisor, without opening every student's report individually.

---

## Key design decisions

**Department scoping is enforced at three levels, not one.**
1. *Form level* — a coordinator's or supervisor's department dropdown is rendered `disabled`, showing only their one real department.
2. *Model level* — `CustomUser.clean()` refuses to save a student with no department, a coordinator with no faculty, or a supervisor with no `supervisor_department`. This runs on every full save, and on any partial save that touches those specific fields — but deliberately *not* on Django's own internal `last_login` timestamp update, since that would otherwise lock legacy accounts with missing data out of logging in entirely.
3. *Query level* — every dashboard, list, and report filters by `student__department=dept` or `posted_by=coordinator`, never trusting that the form-level lock alone is sufficient (a raw POST request could bypass a disabled HTML field; the query-level filter is what actually protects the data).

**Company/supervisor pairing can never mismatch, by construction.** Placements only ever originate from a supervisor's own account, so `company_name` and `assigned_supervisor` are always internally consistent — there's no free-text field or open dropdown anywhere that could pair a placement with an unrelated company.

**Every stat-producing view shares one context-building function between its screen version and its print/PDF version.** This came directly out of a bug where the PDF version had silently duplicated the entire aggregate report's logic by hand, computing everything twice per request and risking the two views drifting apart over time.

**Notifications are polling-based, not WebSocket-based, by deliberate choice.** Django Channels (real-time push) was considered and explicitly ruled out in favour of a simple `fetch()` poll every few seconds. The visible result is nearly identical — a badge counter, toast popups, sound — but polling stays entirely within the request/response model the rest of the project already uses, with no new infrastructure (ASGI, channel layers, async consumers) and a far easier failure mode to diagnose.

**Role identity is visual, not just structural.** Each role has one accent color used consistently across its sidebar, buttons, and form focus states — Admin (violet), Coordinator (teal), Supervisor (rust), Student (rose) — plus a shared heading typeface (Space Grotesk) distinct from the default Bootstrap look. The login and registration pages carry an illustrated background panel; the registration panel's colour and copy shift live as a role is selected, before the form is even submitted.

---

## Setup

```bash
# Clone and enter the project
cd internship_system

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Create a superuser (for /admin/ access)
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

### Password reset (development)

Password reset emails are **not** sent over real SMTP in development — `EMAIL_BACKEND` is set to Django's console backend, meaning the full reset email (including the working link) prints straight to the terminal running `runserver`. No email account setup is required to test the flow locally.

### Seeding assessment criteria

`AssessmentCriteria` rows are meant to be seeded (via a management command or manually through `/admin/`) before any supervisor can submit an assessment — the scoring form has nothing to render until at least one active criterion exists.

---

## Known limitations / in progress

- **Notifications app is mid-build and not yet functional.** The `Notification` model, admin registration, and polling endpoint scaffolding exist, but the app was not yet confirmed to register correctly in `INSTALLED_APPS` at the time of writing — it does not yet appear in `/admin/`. The navbar bell, toast popups, and live badge counter described in the original spec have not been wired into `base.html` yet.
- **"Behind on logbook" reminders** are not yet automated. Every other notification trigger (application accepted, log reviewed, assessment submitted, announcement posted) fires from inside an existing view. "Student hasn't logged in N days" is a standing condition, not a one-off event, and needs a scheduled management command rather than a page-load trigger — this has not been built yet.
- **Legacy data note**: a handful of placements created before the supervisor-submission workflow existed were manually corrected via Django shell during development (missing or mismatched supervisors, department-name inconsistencies like "School of Computing" vs "Computer Science"). Going forward, this class of problem should not recur, since every new placement is locked correctly from the moment it's created.

---

## Notes for future development

A few recurring gotchas worth knowing before editing this codebase further:

- **A disabled Django form field is not automatically disabled in the rendered HTML** if a template hand-writes the `<select>`/`<input>` instead of using `{{ form.field }}`. The `disabled` attribute has to be added explicitly in the template (`{% if form.field.field.disabled %}disabled{% endif %}`), or the field will look editable even though Django ignores whatever value is submitted for it server-side.
- **`get_or_create()` only applies its `defaults` on first creation.** If a related field (like which supervisor owns a draft assessment) needs to stay in sync after the fact — say, a supervisor reassignment — that has to be handled explicitly on every fetch, not assumed from the original creation.
- **Keep one function name per file.** Pasting an updated version of a function without deleting the old one lets Python silently keep whichever definition comes last with no warning — this has caused more than one confusing bug during development. When editing a view, confirm with a text search that the function name appears exactly once before saving.
- **Check which app's `views.py` is actually open before pasting.** Several apps (`accounts`, `placements`, `logbook`, `assessment`, `reports`) all have a file literally named `views.py`; the tab label alone doesn't distinguish them. Check the breadcrumb path at the top of the editor before editing.