# Update an existing Railway deployment to YOUSSEF.COM v9.3

YOUSSEF.COM v9.3 adds server-enforced roles and the Admin-only Users & Roles page, plus a sidebar background fix when scrolling.

## Keep these Railway settings unchanged
- Existing Railway project/service
- Existing `/data` persistent volume
- Existing generated Railway domain
- `DATA_DIR=/data`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `SECRET_KEY`

## Update GitHub
Replace these files in the existing private `youssef-com` repository:
- `server.py` (required)
- `README.md`
- `UPDATE_EXISTING_RAILWAY.md`

You do not need to upload a database file. Production data belongs in Railway `/data/youssef.db` and `*.db` is ignored by Git/Docker.

After committing, Railway should redeploy automatically. Wait until the latest deployment is `ACTIVE / Deployment successful`, then hard refresh with `Ctrl + F5`.

## Roles
### Admin
Full access, including **Users & Roles**.

### Manager
Operational access to months, imports, media buyers, adjustments, products, commission rules, African upsells, city mappings, reviews, rates and exports. Cannot access user/security administration.

### Media Buyer Viewer
Read-only. Must be linked to one media buyer and can only view that buyer's own monthly dashboard and own month history. Team lists, imports, settings, exports and administrative pages are blocked server-side.

## Create users
Sign in as Admin, open **Users & Roles** in the left menu, then create Manager or Media Buyer Viewer accounts. Viewer accounts must be linked to a media buyer.

## Important security note
If `youssef.db` was previously uploaded and committed to GitHub, delete it from the repository. The Railway app does not need that tracked file because production data is stored on the `/data` volume.
