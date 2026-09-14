# Update an existing Railway deployment to YOUSSEF.COM v9.2

1. Keep the existing Railway project, `/data` volume, variables and public domain.
2. Upload/replace **server.py** from this package in the root of the same GitHub repository.
3. You may also replace README.md. No database file needs to be uploaded.
4. Commit the change. Railway should redeploy automatically.
5. Wait for Deployment successful / Active.
6. Open `/login` and hard refresh with Ctrl+F5.

v9.2 embeds the full CSS directly in server.py, so the interface does not rely on Railway serving a static CSS file.
