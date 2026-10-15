# SmartHostel — Azure App Service deployment fix

This ZIP is structured for **Linux Azure App Service**: `app/`, `requirements.txt`, and `static/` are at the deployment root. That fixes `ModuleNotFoundError: No module named 'app'`, which occurs when Azure starts Uvicorn from a directory that does not contain the `app` package.

## Azure settings
1. App Service → **Configuration / Environment variables**. Set `DATABASE_URL` to the PostgreSQL server owned by your friend, using the exact hostname, database name and username they provide. Use `?sslmode=require`. URL-encode special characters in the password (`@` → `%40`, `:` → `%3A`, `/` → `%2F`, `#` → `%23`, `%` → `%25`). Do not include surrounding quotes.
2. Set `JWT_SECRET` to a newly generated long random value.
3. Set `WEBSITE_RUN_FROM_PACKAGE` only if required by your chosen deployment method; do not set it to a guessed local path.
4. Use Python 3.12 (the app currently targets that stack). Set Startup Command to: `bash startup.sh` (or use `python -m pip install -r requirements.txt && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`).
5. Deploy the contents of this ZIP to the **root** of `/home/site/wwwroot`, not a nested `backend/` or `dbms/project/backend/` directory.
6. Your friend's PostgreSQL server must allow the App Service outbound connection. They must add the App Service outbound IP addresses to the server firewall, and confirm the DB user has the required privileges. Azure PostgreSQL networking/firewall is managed on your friend's server, not your web app.
7. Restart the Web App. Test `https://YOUR-APP.azurewebsites.net/` and `/docs`. If it fails, use App Service → Log stream and check the first traceback.

## Important security action
Credentials and a JWT secret were visible in the screenshots and/or bundled `.env` files. Treat them as exposed: **ask your friend to rotate the PostgreSQL password**, replace `DATABASE_URL` in Azure, and replace `JWT_SECRET` with a new random secret. Remove `.env` files from Git history if they were committed. Never share screenshots with values visible.

## Architecture
Your App Service hosts FastAPI and the built frontend (`static/`). It connects outbound to your friend's PostgreSQL database. The database does not need to be moved to your Azure account. Because the frontend is served by the same app, `/api` calls are same-origin; `ALLOWED_ORIGINS` can remain empty unless you host the frontend on a separate domain.
