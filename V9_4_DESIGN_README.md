# YOUSSEF.COM v9.4 — refreshed design candidate

This is the full Python application source from the v9.4 test build, with an updated responsive UI, sidebar color continuity, card interactions, smoother page transitions, accessible focus states, and reduced-motion support.

**Not a Netlify drag-and-drop app:** Python + SQLite requires a persistent Python hosting service such as Railway. Netlify can serve a frontend, but this ZIP does not provide a Netlify-hosted backend.

**Do not replace production yet:** Real Excel quantity imports, currency rate history, offer-edit historical immutability and migration reconciliation are not fully validated. Do not overwrite `/data/youssef.db`.

To run locally: install requirements, set ADMIN_EMAIL/ADMIN_PASSWORD/SECRET_KEY and DATA_DIR, then `python server.py`. Use a test DATA_DIR.

The v9.4 frontend preview on Netlify is a separate browser-only prototype, not this backend.
