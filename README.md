# YOUSSEF.COM v9 Online Edition
Cloud-ready evolution of v8. Preserves periods, cumulative negative-credit logic, team-leave status, dated commissions, persistent city mappings, African upsell approval, Morocco upsells, imports, analytics and Excel export.

## Online additions
- Binds to `0.0.0.0` and Railway `PORT`.
- Persistent data path controlled by `DATA_DIR` / `DB_PATH`.
- Passwords stored with PBKDF2 hashes rather than plaintext.
- Roles: ADMIN, MANAGER, MEDIA_BUYER_VIEWER.
- Viewer role is read-only; accounts can be linked to a media buyer.
- Dockerfile + railway.toml included.
- `manage_users.py` creates/updates accounts.
- See `DEPLOY_RAILWAY.md` for deployment.

Important: mount Railway persistent storage at `/data`. Without a persistent volume, SQLite data can disappear on redeploy.
