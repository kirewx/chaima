# Admin-Generated Password Reset Links

## Problem

A user who forgets their password has no way back into ChAiMa. There is no self-service reset and no operator path short of editing the database: the documented workaround is to generate a hash with `docker compose exec chaima python -c "…PasswordHelper().hash('…')"` and write it into `user.hashed_password` with `sqlite3`. That is error-prone, requires shell access to the host, and leaves no record that it happened.

The obvious fix — emailing a reset link — is blocked on infrastructure. Outbound SMTP was measured from the production VPS on 2026-08-07: ports 25, 465 and 587 are silently dropped (connection attempts time out rather than being refused), against Gmail, SendGrid, Brevo, Mailgun and Mailjet alike. Only port 2525 is open. Mail is therefore possible but requires a relay account, sender-domain SPF/DKIM records, and a non-default port — none of which should gate the ability to recover an account.

`UserManager` already declares `reset_password_token_secret` (`src/chaima/auth.py:26`), but no reset router is mounted and no `on_after_forgot_password` hook exists, so the capability is inert.

## Solution

A group administrator generates a single-use reset link for a member from the members list and delivers it out of band — in person, by chat, however they already reach that person. The link opens a public page where the user sets a new password.

The token is the one `fastapi-users` already produces. `UserManager.forgot_password()` (`.venv/…/fastapi_users/manager.py:358`) builds a JWT carrying `sub`, `aud` and a `password_fgpt` — a hash of the user's *current* `hashed_password`. On redemption, `reset_password()` re-verifies that fingerprint against the hash in the database (`manager.py:425`). Changing the password therefore invalidates every outstanding token for that user automatically. Single use costs no bookkeeping of our own, so no token table is introduced.

What the library does not give us is a record of who issued a link for whom. Because issuing a reset link is equivalent to handing over the account, that record matters, and it is written to the existing `event` table rather than to a new one.

## Scope

In scope:

- A permission rule that prevents an administrator from resetting an account they do not fully control.
- `POST /api/v1/groups/{group_id}/members/{user_id}/reset-link` returning a token, a URL and an expiry.
- `POST /api/v1/auth/reset-password` redeeming a token against a new password.
- A public `/reset-password/:token` page and a menu entry in the members list.
- Two audit event types.
- Session lifetime raised from one hour to 30 days, configurable.

Explicitly out of scope:

- **Email delivery.** Added later as `POST /api/v1/auth/forgot-password`. The token format and the redemption endpoint specified here are exactly what that flow needs, so the addition is purely additive.
- **A CLI recovery command.** If the only superuser forgets their password, the `sqlite3` workaround remains. Deferred by explicit decision.
- **Server-side session invalidation.** Decided against explicitly; see Session Lifetime and Known Limitations.
- **Revocation of an issued link.** A link is invalidated by issuing and redeeming another one, or by waiting out the TTL.

## Permission Rule

Issuing a reset link grants control of the target account. Users belong to groups through `UserGroupLink` and may belong to several. An unrestricted rule would therefore let an administrator of group A take over a member who also belongs to group B and read B's data through that account; targeting a superuser would compromise the whole instance.

The rule, implemented as `services/password_reset.py::assert_may_reset(session, actor: User, target: User)`:

1. If the actor is a superuser — allowed.
2. Otherwise, if the target is a superuser — denied.
3. Otherwise — allowed only if every group the target belongs to is a group in which the actor holds `is_admin`.

A target with no memberships is allowed under rule 3: the empty set is a subset of anything, and a user removed from all groups is a real case.

Denial is `403` with a message naming the reason, so the frontend can explain it rather than showing a bare failure.

Separately, and independently of this rule, the endpoint must confirm that the target is a member of the group named in the path. `GroupAdminDep` only proves the caller administers `{group_id}`; without this check a caller could put an arbitrary user ID in the path. A target that is not a member of that group is `404`.

## Session Lifetime

Sessions currently last one hour. Two values enforce that, and both must move together: `cookie_max_age=3600` on the `CookieTransport` (`auth.py:77`) and `lifetime_seconds=3600` on the `JWTStrategy` (`auth.py:84`). Raising only the first leaves the browser holding a cookie whose token has already expired; raising only the second has the browser discard a token that is still valid. Both are driven from one setting so they cannot drift apart.

The new default is **30 days**. Users reach ChAiMa from a phone and a desktop and should not have to re-authenticate on every visit.

Sessions remain **stateless**: the signed JWT is the whole session, and no server-side record of issued tokens is kept. Switching to `DatabaseStrategy` — supported by the already-installed `fastapi_users_db_sqlalchemy` 7.0.0, which ships an `accesstoken` table — would make sessions revocable and was considered and rejected for this iteration. The consequences are recorded under Known Limitations rather than left implicit, because a 30-day stateless session materially changes what the reset feature in this spec can accomplish.

## Backend Changes

### Config (`config.py`)

Add to `Settings`, beside `cookie_secure` (`config.py:17`):

- `session_ttl_hours: int = 720` → `CHAIMA_SESSION_TTL_HOURS`. 720 hours is 30 days.

Add to `AdminSettings`, beside the existing `invite_ttl_hours` (`config.py:57`):

- `password_reset_ttl_hours: int = 24` → `CHAIMA_PASSWORD_RESET_TTL_HOURS`.

The `fastapi-users` default for reset tokens is one hour (`manager.py:33`). That is sensible for a link mailed to someone at their desk and too short for one handed over by hand, so it is raised to 24 hours and made configurable. Note that this is a separate knob from `session_ttl_hours`: how long a recovery link stays usable and how long someone stays logged in are unrelated questions.

### Session configuration (`auth.py`)

Feed `settings.session_ttl_hours * 3600` into both `CookieTransport(cookie_max_age=...)` and `JWTStrategy(lifetime_seconds=...)`.

### Token generation (`auth.py`)

On `UserManager`:

- Set `reset_password_token_lifetime_seconds` from the new setting.
- Add `generate_reset_token(self, user: User) -> str`, building the same claims as `forgot_password()` — `sub`, `password_fgpt`, `aud` — via `generate_jwt`.

A separate method rather than a call to `forgot_password()`: that method does not return the token, it passes it to `on_after_forgot_password`. Recovering the value by overriding the hook would be indirection in service of nothing. The duplicated claim construction is three lines and stays adjacent to the library call it mirrors.

### Service (`services/password_reset.py`)

`assert_may_reset` as specified above, raising a dedicated exception that the router maps to `403` — matching how `services/invites.py` raises `InviteExpiredError` and friends for `routers/invites.py` to translate.

### Endpoints

`POST /api/v1/groups/{group_id}/members/{user_id}/reset-link` in `routers/groups.py`, beside the existing member routes (`groups.py:264`, `groups.py:304`). It takes both `GroupAdminDep` — which proves the caller administers the group in the path — and `CurrentUserDep`, since the permission rule needs the actor's `User` to test `is_superuser`. Returns `ResetLinkRead { token, reset_url, expires_at }`, where `expires_at` is computed as issue time plus `password_reset_ttl_hours`, mirroring the `exp` claim the JWT carries, and is returned for display only.

`reset_url` is built exactly as `_to_invite_read()` builds invite URLs (`routers/invites.py:26-33`): `f"{public_base_url}/reset-password/{token}"`, or `null` when the setting is unset, in which case the frontend falls back to `window.location.origin`.

`POST /api/v1/auth/reset-password` in a new `routers/password_reset.py`, taking `{ token, password }`, calling `user_manager.reset_password(...)` and mapping `InvalidResetPasswordToken`, `UserNotExists` and `UserInactive` to `400`, and `InvalidPasswordException` to `400` with the validation reason.

This is written by hand rather than mounted from `fastapi_users.get_reset_password_router()` because that router also exposes `/forgot-password`, which without mail delivery would return `202` and do nothing. An endpoint that reports success and has no effect is worse than an absent one.

There is deliberately **no** endpoint to inspect a reset token before redemption, unlike `GET /api/v1/invites/{token}`, which the invite page uses to show validity and group name up front. Such an endpoint would let anyone probe whether a token is live. The reset page shows its form unconditionally and reports the outcome only on submit.

### Audit events

Two constants added to `EventType` (`models/analytics.py:12`). Values are stored as plain strings by design, so no migration is required (`models/analytics.py:15`).

- `password_reset_link_created` — written on issue, via `_persist_event` (`services/events.py:21`). `user_id` is the **administrator who issued it**, `group_id` the group from the path, `payload` `{"target_user_id": "<uuid>"}`. The actor rather than the target, because the question asked afterwards is who authorised this.
- `password_reset_completed` — written on successful redemption. `user_id` is the affected user, `group_id` is `null`.

`_persist_event` swallows its own exceptions, so a failing audit write cannot break either request.

## Frontend Changes

### Hooks (`api/hooks/usePasswordReset.ts`)

New file following `useInvites.ts`:

- `useCreateResetLink(groupId)` — mutation posting to `/groups/{groupId}/members/{userId}/reset-link`.
- `useResetPassword()` — mutation posting `{ token, password }` to `/auth/reset-password`.

### Members list (`components/settings/MembersInvitesSection.tsx`)

A third entry, "Generate password reset link", in the `MemberRow` action menu (`MembersInvitesSection.tsx:142`). It opens a dialog reusing the invite dialog's shape — read-only `TextField` holding the URL, copy button, snackbar confirmation.

The dialog's wording must differ from the invite dialog's "Share this link. It is valid once." A reset link is account takeover in text form; the copy states that it grants access to the account and should be delivered directly to that person.

The entry is shown for every member rather than hidden when the permission rule would reject it. The client cannot evaluate the rule — it does not know the target's other memberships — and computing a `can_reset_password` flag per row would mean an extra query per member. In the deployments this serves, nearly every user belongs to exactly one group, so rejection is rare. The `403` message is surfaced in the dialog instead. The flag can be added later if this proves annoying in practice.

### Reset page

Route `/reset-password/:token` in `App.tsx`, beside `/invite/:token` (`App.tsx:15`) and likewise outside `ProtectedRoute` — the user is locked out by definition.

`pages/ResetPasswordPage.tsx`: new password and confirmation fields, client-side equality check, submit, then a success notice and redirect to `/login`. A `400` renders as "This link is invalid or has expired."

### Login page (`pages/LoginPage.tsx`)

One unobtrusive line beneath the form: password recovery runs through the user's group administrator. With no mail delivery there is no self-service path, and saying so plainly beats letting users hunt for one.

## Known Limitations

**A password change does not end existing sessions, and sessions now last 30 days.** The session is a stateless signed JWT; nothing consults the database on each request, so a token issued before a reset stays valid until its own expiry. Resetting a password therefore does not evict anyone who is already logged in — for up to 30 days.

This is the deliberate trade for not keeping server-side session state, and it has three consequences worth naming plainly:

- The reset feature specified here recovers *access* for a user who is locked out. It is not a remedy for a compromised account, because it does not revoke the attacker's existing session.
- Logout clears the cookie in the browser but does not invalidate the token. Anyone who captured the token beforehand can keep using it until it expires.
- A token leaked from a device now has a 30-day useful life rather than one hour.

The escape hatch, should any of this become a real problem, is `DatabaseStrategy` with the `accesstoken` table from `fastapi_users_db_sqlalchemy`: it makes logout effective, allows a reset to drop every session belonging to the user, and costs one indexed primary-key lookup per request. The change is contained to `auth.py` plus one migration and does not disturb anything specified here, so deferring it forecloses nothing.

Until then, the operational answer for a genuinely compromised account is to reset the password and change `CHAIMA_SECRET_KEY`, which invalidates every session on the instance at once.

**Issued links cannot be revoked before expiry.** Accepted as the cost of holding no token table. The exposure is bounded by the TTL and by automatic invalidation on the next successful password change.

## Files to Change

Backend:

- `src/chaima/config.py` — `session_ttl_hours`, `password_reset_ttl_hours`
- `src/chaima/auth.py` — session lifetime on both transport and strategy, reset token lifetime, `generate_reset_token`
- `src/chaima/services/password_reset.py` — new, permission rule
- `src/chaima/schemas/password_reset.py` — new, `ResetLinkRead`, `PasswordResetPerform`
- `src/chaima/routers/groups.py` — issue endpoint
- `src/chaima/routers/password_reset.py` — new, redeem endpoint
- `src/chaima/app.py` — mount the new router
- `src/chaima/models/analytics.py` — two `EventType` constants

Frontend:

- `frontend/src/api/hooks/usePasswordReset.ts` — new
- `frontend/src/pages/ResetPasswordPage.tsx` — new
- `frontend/src/App.tsx` — route
- `frontend/src/components/settings/MembersInvitesSection.tsx` — menu entry and dialog
- `frontend/src/pages/LoginPage.tsx` — recovery hint
- `frontend/src/types/index.ts` — response types

No migration: no schema change.

## Testing

`tests/test_services/test_password_reset.py` — the permission rule in isolation:

- superuser actor is always permitted
- superuser target is always refused
- subset satisfied → permitted
- target additionally in a group the actor does not administer → refused
- target with no memberships → permitted

`tests/test_api/test_password_reset.py` — the path through the API:

- group admin issues a link; response carries token and URL
- plain member issuing → `403`
- admin of A targeting a user who also belongs to B → `403`
- target who is not a member of the group in the path → `404`
- valid token redeemed → `200`, and a subsequent login with the new password succeeds
- the same token redeemed twice → second attempt `400`, since `password_fgpt` no longer matches the stored hash. This is the test that pins the single-use property the design relies on.
- tampered and expired tokens → `400`
- both event types are written, following the pattern in `tests/test_api/test_admin_analytics_writes.py` and `tests/test_services/test_auth_login_hooks.py`

`tests/test_config.py` — session lifetime:

- `cookie_max_age` on the transport and `lifetime_seconds` on the strategy both derive from `session_ttl_hours` and are equal. Cheap, and it pins the one failure mode of this change: the two values silently drifting apart.

No frontend e2e tests are added. Nine e2e tests are already failing on `main` for unrelated historical reasons; adding to that suite would park new tests where nobody is currently looking.
