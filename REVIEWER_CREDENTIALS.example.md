# Reviewer credentials (EXAMPLE — safe to commit)

Copy this file to a **gitignored** local credentials file and use the demo keys
from `.env.example` / your local `.env`.

## Create your local credentials file

```powershell
Copy-Item REVIEWER_CREDENTIALS.example.md REVIEWER_CREDENTIALS.md
# or
Copy-Item REVIEWER_CREDENTIALS.example.md .local/reviewer_credentials.env
```

`REVIEWER_CREDENTIALS.md` and `.local/` are gitignored and must never be committed.

## Demo principals (replace with values from your local `.env`)

| Role | Subject | Login method | Example credential |
|---|---|---|---|
| Farmer | `farmer-asha` | Email OTP (preferred), Google demo, or API key | `farmer-demo-key-0123456789abcdef` · `asha.patil@demo.sasyaai.local` |
| Extension Officer (West) | `officer-west` | API key or email OTP | `officer-west-demo-key-0123456789ab` · `officer.west@demo.sasyaai.local` |
| Extension Officer (South) | `officer-south` | API key or email OTP | `officer-south-demo-key-0123456789a` · `officer.south@demo.sasyaai.local` |
| System Admin | `system-admin` | API key or email OTP | `admin-demo-key-0123456789abcdef0` · `admin@demo.sasyaai.local` |

### Farmer signup / passwordless

1. Open the UI as **Farmer**.
2. Prefer **Email OTP**, **Continue with Google (demo)**, or **Register new farmer**.
3. API key is under **Advanced / reviewer API key** and is optional for farmers.
4. After signup/login the UI stores the session token and attaches it to every desk API call.

### OTP flow

1. Open the UI → choose a role → enter email → Request OTP.
2. Local/demo/synthetic responses include `otp_demo_code`.
3. Submit the code → session token is stored for API calls.
4. Newly registered farmer emails can re-login with OTP (no API key needed).

### Farmer signup

Use **Register new farmer** on the login screen. After onboarding, the API returns a farmer-scoped session token, persists the profile under `var/registered_farmers.json`, and assigns the farmer to the regional officer automatically.

These keys are **demo-only**. Rotate before any shared or production deployment.
