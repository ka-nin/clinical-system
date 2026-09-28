# Deploying the CareBoard demo to Wasmer Edge

This puts the **demo** online: a warning banner, demo accounts, no email, no two-step sign-in.
It is for showing the project, **not for real patients**.

The database is **MySQL, created and managed by Wasmer**. You don't install anything for it.
On first start the app creates its tables and adds the demo accounts by itself.

## 1. One-time setup
```bash
curl https://get.wasmer.io -sSfL | sh      # install the Wasmer CLI (see https://docs.wasmer.io/install)
wasmer login
```

## 2. Build the clean deploy folder
Run this from the project root every time you want to deploy changes:
```bash
./tools/build_deploy.sh
```
It creates:
- `build/deploy/`: only the files the website needs. Your local database, tests, design files,
  `demo-accounts.txt` and `.env` are left out.
- `build/deploy-secrets.env`: the secret key and the **demo password** (created once, kept between builds).
  It is outside the deploy folder, so it is never uploaded. Don't share it or commit it.

## 3. Deploy
```bash
cd build/deploy
wasmer deploy
```
- The first time, the CLI asks for an app name and owner. Accept or choose a name.
- If it says it doesn't understand `app.yaml`: rename it to `app.yaml.ours`, run `wasmer deploy`
  again so Wasmer writes its own, then copy the `capabilities:` and `env:` parts from `app.yaml.ours` into it.

## 4. Add the secrets, then redeploy once
```bash
wasmer app secrets create --from-file ../deploy-secrets.env
wasmer deploy
```
Without these the app refuses to start on purpose (no secret key = unsafe sign-ins).

## 5. Check it
- Open `https://<your-app>.wasmer.app/login/`. The yellow "Demo system" bar should be at the top.
- Sign in as `admin@careboard.demo` with the `DEMO_PASSWORD` from `build/deploy-secrets.env`.
- **Privacy:** on wasmer.io, open your app/package settings and make sure the package is **private**.
  If it's public, anyone could download the uploaded code.

## 6. Give your friends access
Best: sign in as the admin, go to **User Management → Add New User Instance**, and make one account per friend.
You'll see a temporary password once. Send it to them, and they can change it under **Change password**.
Or share a demo login (all demo accounts use the `DEMO_PASSWORD`):

| Role | Email |
|---|---|
| Physician | dr.henderson@careboard.demo |
| Nurse | nurse.reyes@careboard.demo |
| Receptionist | sarah.cole@careboard.demo |
| Student | student@careboard.demo |
| Administrator | admin@careboard.demo (keep this one to yourself) |

## Good to know
- Redeploying keeps all data. To start over with fresh demo data, delete the app's database in the Wasmer
  dashboard; the app recreates it on the next start.
- Emails (password reset, approvals) are not sent in demo mode; they are written to the app log.
- Tested locally: the exact `build/deploy` folder, run with gunicorn and production settings against an empty
  MySQL 8 database, sets itself up and signs in. **Not yet tested on Wasmer itself**: if a step above fails,
  copy the error from `wasmer app logs` and ask for help.
