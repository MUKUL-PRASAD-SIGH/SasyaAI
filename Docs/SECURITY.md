# 🔐 SECURITY — SasyaAI

---

## 1. Security Principles

- **Privacy by Design**: Minimal data collection, purpose limitation, consent-first
- **Zero Trust**: Every service authenticates every request; no implicit trust inside the cluster
- **Defense in Depth**: Multiple overlapping security controls at each layer
- **DPDP Compliance**: Aligned with India's Digital Personal Data Protection Act, 2023

---

## 2. Authentication & Authorization

### Farmer Authentication Flow

```
Farmer App
    │
    ▼
Mobile OTP (Aadhaar-linked number)
    │
    ▼
DigiLocker eKYC (optional, for scheme applications)
    │
    ▼
JWT Access Token (15-min TTL) + Refresh Token (30-day TTL)
    │
    ▼
Kong API Gateway (token validation on every request)
    │
    ▼
Service-level RBAC check
```

### Role-Based Access Control (RBAC)

| Role | Permissions |
|---|---|
| `farmer` | Read/write own digital twin, submit images, view own recommendations |
| `extension_officer` | Read digital twins of assigned farmers, broadcast advisories |
| `fpo_admin` | View anonymized cluster analytics for their FPO |
| `policy_analyst` | Read-only access to anonymized district/state aggregates |
| `system_admin` | Full access to configuration, no access to farmer PII by default |

### Service-to-Service Auth
- All internal service communication uses **mTLS** (mutual TLS) via Istio
- Kubernetes Service Accounts with RBAC, no long-lived credentials
- HashiCorp Vault for dynamic secrets rotation

---

## 3. Data Protection

### Encryption at Rest
| Data | Method |
|---|---|
| PostgreSQL (PII fields) | AES-256 column-level encryption (pgcrypto) |
| S3 Buckets | Server-side encryption (SSE-S3) |
| Redis | Encrypted ElastiCache with in-transit TLS |
| Backups | AES-256 encrypted before storage |

### Encryption in Transit
- All external API calls: TLS 1.3 minimum
- Internal K8s traffic: mTLS enforced by Istio
- Mobile app ↔ API: Certificate pinning (HPKP)
- No unencrypted HTTP endpoints (HTTP → HTTPS redirect enforced)

### PII Data Minimization

| Field | Storage Strategy |
|---|---|
| Aadhaar number | Never stored; only token reference from UIDAI |
| Mobile number | Hashed (SHA-256 + salt) for identity; masked in logs |
| Full name | Encrypted at rest; access logged |
| Land parcel data | Linked via AgriStack token, not stored locally |
| GPS coordinates | Rounded to 100m precision for anonymization |
| Financial data | Encrypted; accessed only by planning agent |

---

## 4. Threat Model

### Key Threats & Mitigations

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Unauthorized farmer data access | Medium | High | RBAC + audit logs + data encryption |
| AI prompt injection via farmer input | Medium | Medium | Input sanitization + sandboxed LLM calls |
| AgriStack API credential theft | Low | Critical | Vault-managed secrets + short TTL tokens |
| Model poisoning (adversarial images) | Low | Medium | Input validation + confidence thresholding |
| DDoS on advisory endpoints | Medium | Medium | Cloudflare rate limiting + WAF |
| Insider threat (admin data exfil) | Low | High | Break-glass access + immutable audit log |
| MITM on mobile app traffic | Low | High | Certificate pinning + TLS 1.3 |
| False advisory liability | Medium | High | Confidence gates + disclaimer + human escalation |

---

## 5. Security Monitoring

### SIEM & Alerting
- **AWS CloudTrail + GuardDuty**: Cloud infrastructure anomaly detection
- **Falco**: Runtime container security (detects unexpected syscalls)
- **WAF (AWS WAF / Cloudflare)**: OWASP Top 10 protection, bot management
- **Prometheus Alertmanager**: Security metric alerts (auth failures, rate limit hits)

### Key Security Metrics

```
auth_failure_rate          # > 10/min per IP → auto-block
suspicious_query_patterns  # SQL injection patterns
api_rate_limit_breaches    # Per-farmer and per-IP
pii_access_frequency       # Unusual bulk PII reads
model_input_anomaly_score  # Adversarial image detection
```

### Audit Logging

All of the following are logged immutably to CloudWatch + S3:
- Every farmer profile access (who, when, what fields)
- Every AI recommendation generated and delivered
- Every scheme eligibility check
- Every admin action on the platform
- All authentication events (success and failure)

---

## 6. Vulnerability Management

### Dependency Scanning
- **Dependabot** (GitHub): Automated PRs for vulnerable dependencies
- **Trivy**: Docker image vulnerability scans in CI pipeline
- **Bandit**: Python static analysis for security issues
- Weekly OWASP ZAP dynamic scan on staging

### Penetration Testing
- Quarterly internal pen test
- Annual third-party security audit before major releases
- Bug bounty program (planned for post-MVP launch)

---

## 7. DPDP Act 2023 Compliance

| Requirement | Implementation |
|---|---|
| Consent before data collection | Explicit consent UI at onboarding; granular consent per data type |
| Purpose limitation | Data use restricted to agricultural advisory; contractual with all sub-processors |
| Right to erasure | Farmer can delete account + data within 30 days |
| Right to data portability | Export full digital twin as JSON via in-app request |
| Data localization | All PII stored in AWS ap-south-1/ap-south-2 (India) only |
| Breach notification | Automated detection + CERT-In notification within 6 hours |
| Data Fiduciary registration | Registered as Significant Data Fiduciary (planned) |

---

## 8. Incident Response

### Severity Levels

| Level | Definition | Response Time |
|---|---|---|
| P0 (Critical) | Active breach, PII exfiltration | 15 minutes |
| P1 (High) | Auth bypass, service down | 1 hour |
| P2 (Medium) | Unusual access patterns, model anomaly | 4 hours |
| P3 (Low) | Non-critical vulnerability, performance | 24 hours |

### Response Playbook (P0)
1. **Detect**: GuardDuty / Falco alert fires
2. **Contain**: Auto-revoke affected tokens + isolate namespace
3. **Assess**: Security engineer reviews audit logs
4. **Notify**: Farmers and CERT-In (if PII breach) within 6 hours
5. **Remediate**: Patch + rekey + redeploy
6. **Review**: Post-incident report within 48 hours

---

## 9. Consent Framework

SasyaAI operates on an **informed, granular, revocable consent model** aligned with DPDP Act 2023.

### Consent Categories

| Category | Data Types | Default | Revocable |
|---|---|---|---|
| Core Service | Farmer ID, land records, crop history | Mandatory (no service without) | Yes (account deletion) |
| Personalization | Soil health, input preferences, financial goals | Opt-in | Yes, any time |
| Location Services | GPS coordinates (100m precision) | Opt-in | Yes, any time |
| Market Data | Purchase history, market linkages | Opt-in | Yes, any time |
| Research/Analytics | Anonymized usage patterns | Opt-out | Yes, any time |
| Communication | Push notifications, SMS alerts | Opt-in | Yes, any time |

### Consent Capture Flow

```
New Farmer Onboarding
        │
        ▼
Step 1: Core Consent Screen
• Plain-language explanation (regional language)
• Audio narration option for low-literacy users
• "I Agree" + "Learn More" options
        │
        ▼
Step 2: Optional Features Consent
• Toggle-based (each category clearly explained)
• Benefits of each consent clearly stated
        │
        ▼
Step 3: Consent Receipt
• Timestamped consent record stored (immutable)
• Copy sent to farmer's registered mobile
        │
        ▼
Ongoing: Consent Management
• "My Privacy Settings" in profile → edit any time
• Withdrawal takes effect within 24 hours
• Data deletion request processed within 30 days
```

---

## 10. Detailed Permission Matrix

### Data Access Permissions

| Data Category | Farmer (self) | Extension Officer | FPO Admin | Policy Analyst | System Admin |
|---|---|---|---|---|---|
| Own farmer profile | ✅ Read/Write | ✅ Read | ❌ | ❌ | ✅ Read |
| Others' farmer profiles | ❌ | ✅ Assigned only | ❌ | ❌ | ✅ Read (logged) |
| Soil health data | ✅ | ✅ | ❌ | Anonymized | ✅ |
| Financial profile | ✅ | ❌ | ❌ | ❌ | ❌ |
| Scheme eligibility | ✅ | ✅ | ❌ | Aggregated | ✅ |
| AI recommendations | ✅ Own | ✅ Assigned | ❌ | Aggregated | ✅ |
| Market prices | ✅ | ✅ | ✅ | ✅ | ✅ |
| Pest/disease alerts | ✅ Own | ✅ District | ✅ FPO area | ✅ | ✅ |
| Audit logs | ❌ | ❌ | ❌ | ❌ | ✅ (own actions) |
| System config | ❌ | ❌ | ❌ | ❌ | ✅ |

### Action Permissions

| Action | Farmer | Ext. Officer | FPO Admin | Policy Analyst | System Admin |
|---|---|---|---|---|---|
| Submit pest image | ✅ | ✅ | ❌ | ❌ | ❌ |
| Request crop plan | ✅ | ✅ on behalf | ❌ | ❌ | ❌ |
| Apply for scheme | ✅ | ✅ assist | ❌ | ❌ | ❌ |
| Send broadcast advisory | ❌ | ✅ Own cluster | ✅ Own FPO | ❌ | ✅ |
| Export farm data | ✅ Own | ❌ | ❌ | ❌ | ✅ (with approval) |
| Delete account/data | ✅ Own | ❌ | ❌ | ❌ | ✅ (with farmer consent) |
| View analytics | Limited | District | FPO | State/National | Full |
| Manage users | ❌ | ❌ | Own FPO users | ❌ | ✅ |
| Configure agents | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 11. API Permission Scopes (OAuth2)

```
sasyaai:farmer:read          - Read own farmer profile
sasyaai:farmer:write         - Update own profile
sasyaai:advisory:read        - View recommendations
sasyaai:advisory:request     - Trigger new advisory generation
sasyaai:vision:submit        - Submit images for pest detection
sasyaai:scheme:check         - Check scheme eligibility
sasyaai:scheme:apply         - Initiate scheme application
sasyaai:market:read          - View market prices
sasyaai:analytics:district   - Read district-level aggregates (officers)
sasyaai:analytics:state      - Read state-level aggregates (policy)
sasyaai:admin:users          - Manage user accounts (admin)
sasyaai:admin:config         - Configure system parameters (admin)
```

---

## 12. Data Sharing Policy

### Third-Party Data Sharing

| Recipient | Data Shared | Purpose | Legal Basis |
|---|---|---|---|
| Government (schemes) | Farmer ID + eligibility flag | Scheme enrollment | Legitimate interest + consent |
| Banks / NBFC | Anonymized credit-relevant signals | Credit facilitation | Explicit consent |
| Input companies | Aggregated regional demand signals | Supply planning | Anonymized (no PII) |
| Research institutions | Fully anonymized dataset | Agricultural research | Anonymized (no consent needed) |
| FPO administrators | Member farmer summaries | FPO advisory | Farmer consent |

### What We NEVER Share
- Individual Aadhaar numbers (never stored)
- Individual financial data without explicit consent
- GPS coordinates at better than 100m precision
- Any data with third-party advertisers
- Health or family data

---

## 13. Farmer Rights & Requests

| Right | How to Exercise | SLA |
|---|---|---|
| Access my data | In-app: Profile → My Data → Download | 24 hours |
| Correct my data | In-app: Profile → Edit, or contact support | 72 hours |
| Delete my data | In-app: Profile → Delete Account | 30 days |
| Withdraw consent | In-app: Profile → Privacy Settings | 24 hours |
| Opt out of research use | In-app: Privacy Settings → Research toggle | Immediate |
| Data portability export | In-app: Profile → Export JSON | 48 hours |
| Lodge complaint | Email: privacy@sasyaai.ai | Acknowledged in 24 hours |

**Grievance Officer**: [Name], privacy@sasyaai.ai, +91-XXXXX-XXXXX

