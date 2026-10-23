# YOUSSEF.COM v9.4 — Dark/Light backend candidate

The Python application includes a client-side light/dark toggle (saved per browser). This is **not** a Netlify-only deployable full application. Netlify static drag/drop does not run Python or persist SQLite.

For a fully functioning hosted app, deploy the Python backend to a persistent host with DATA_DIR mounted and configured secrets, or migrate to a serverless-compatible API with managed database. Do not upload this archive to Netlify Drop and expect login, imports, or shared persistence.

This is a candidate build. Validate product import, quantity classification, historical calculation stability, user permissions and backup/migration before using it for payments.
