# YOUSSEF.COM v9.3 Online

Private commission and media-buyer performance platform prepared for Railway.

## v9.3 changes
- Admin-only **Users & Roles** web page.
- Roles: **Admin**, **Manager**, **Media Buyer Viewer**.
- Viewer accounts are linked to one media buyer and are restricted server-side to that buyer's own read-only pages.
- Managers retain operational access but cannot administer users/security.
- User disable/reactivate and password reset controls.
- Role and linked-buyer changes apply to active sessions automatically.
- Sidebar/background remains navy while the main page scrolls.
- Existing v9.2 self-contained CSS remains embedded directly in `server.py` for Railway reliability.

## Railway persistent storage
Set:

`DATA_DIR=/data`

and attach a Railway persistent volume at `/data`.

Production database path:

`/data/youssef.db`

## Required environment variables
- `DATA_DIR=/data`
- `ADMIN_EMAIL=...`
- `ADMIN_PASSWORD=...`
- `SECRET_KEY=...`

## Production note
Do not commit production `youssef.db` to GitHub. Database files are ignored by `.gitignore` and `.dockerignore`; Railway production data should live only on the persistent `/data` volume (plus your backups).
