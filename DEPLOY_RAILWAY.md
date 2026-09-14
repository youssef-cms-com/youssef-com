# Deploy YOUSSEF.COM v9.1 Online on Railway

1. Create a private GitHub repository and upload the contents of this folder.
2. In Railway, create a New Project -> Deploy from GitHub Repo and select the repository.
3. Add a persistent Volume and mount it at `/data`. This is mandatory while v9 uses SQLite.
4. Add Variables: `ADMIN_EMAIL=admin@youssef.com`, `ADMIN_PASSWORD=<a long unique password>`, `DATA_DIR=/data`, `HOST=0.0.0.0`.
5. Deploy. Railway builds the included Dockerfile and starts `python server.py`.
6. In Railway Networking, generate a public domain. Test login and calculations before connecting a custom domain.
7. To preserve your current local history, upload your existing `youssef.db` to the mounted `/data/youssef.db` before production use. Keep an offline backup first.
8. Create staff accounts from the Railway service shell, for example:
   `python manage_users.py --email manager@example.com --name "Manager" --role MANAGER`
   `python manage_users.py --email buyer@example.com --name "Buyer" --role MEDIA_BUYER_VIEWER --buyer "Mohamed Boussous"`
9. Connect a custom domain from Railway Networking (for example `app.youssef.com`) and add the DNS record Railway displays at your domain provider.
10. After the custom domain shows HTTPS, use that URL for production.

Roles in this build: ADMIN and MANAGER can operate monthly workflows; MEDIA_BUYER_VIEWER is read-only. Viewer accounts are linked to a buyer identity for the next fine-grained dashboard restriction layer.

Security: never commit real passwords to GitHub. Use Railway Variables only. Keep the Railway project/repository private and back up `/data/youssef.db` regularly.
