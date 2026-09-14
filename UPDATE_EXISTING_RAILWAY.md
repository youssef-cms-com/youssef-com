# Update an existing Railway v9 deployment to v9.1

You do NOT need to create a new Railway project.

1. Extract this package.
2. In the existing private GitHub repository `youssef-com`, replace/upload the files from this folder.
3. At minimum, `server.py` must be replaced. It is also recommended to upload `.dockerignore`, `.gitignore`, `README.md`, and this file.
4. Commit the changes to the same branch Railway is already watching.
5. Railway should start a new deployment automatically. If not, open the service and choose Redeploy.
6. Do not remove or recreate the `/data` volume.
7. Do not change `DATA_DIR`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, or `SECRET_KEY` unless you intentionally want to change them.
8. When deployment is successful, open the existing Railway URL and hard-refresh the browser with Ctrl+F5.

Your data remains on the attached `/data` volume and is not replaced by this code update.
