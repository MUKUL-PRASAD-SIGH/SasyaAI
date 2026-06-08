# 🧪 AGRISTACK SANDBOX USAGE — SasyaAI

> Complete guide for using the AgriStack Sandbox to develop, test, and validate SasyaAI integrations before production deployment.

---

## 1. What is the AgriStack Sandbox?

The **AgriStack Sandbox** is a secure, government-provided test environment that enables developers, researchers, and stakeholders to access AgriStack APIs with **synthesized (anonymized) datasets** — creating and validating agri-tech solutions without touching real farmer data.

🔗 **Sandbox URL**: [https://sandbox.agristack.gov.in/](https://sandbox.agristack.gov.in/)

### Key Benefits

| Benefit | Description |
|---|---|
| **Risk-Free Testing** | Realistic simulations to evaluate applications before real-world deployment |
| **Privacy-Safe Data** | Synthesized datasets protect farmer privacy while enabling intelligent development |
| **Developer-Friendly** | Welcoming environment to create, test, iterate, and improve digital agricultural solutions |
| **Production Pathway** | Direct migration path from sandbox testing to live production APIs |

### How SasyaAI Uses the Sandbox

SasyaAI relies on the AgriStack Sandbox for:
- Validating Digital Twin creation from farmer registry data
- Testing crop recommendation pipelines against synthesized soil + crop datasets
- Simulating consent flows for data exchange authorization
- Stress-testing API rate limits before production onboarding
- Training team members on AgriStack API structures without production risk

---

## 2. Available API Categories

The sandbox exposes the following API families, each essential to different SasyaAI agents:

### 2.1 Farmer Data APIs
**Used by**: Planning Agent, Orchestrator

Deliver comprehensive farmer information including:
- Demographic profile (name, DOB, gender, caste category)
- Land holdings and cultivated crops
- PM-KISAN ID and scheme linkages
- PAN details and state LGD codes

### 2.2 Land Data APIs
**Used by**: Geospatial Agent

Provide **geo-referenced maps** of land parcels associated with farmers, enabling:
- Farm boundary visualization on interactive maps
- Area calculation for input/output planning
- Parcel-level advisory generation

### 2.3 Crop Data APIs
**Used by**: Planning Agent, Monitoring Agent

Provide **season-specific crop data** mapped to land records, collected through state-level Digital Crop Surveys:
- Crop type and variety planted per parcel per season
- Sowing and harvesting date records
- Historical crop rotation data (5-year rolling)

### 2.4 Aggregated Data APIs
**Used by**: Geospatial Agent, Policy Dashboard

Provide Digital Crop Survey data **aggregated at the village level**:
- Village-level crop coverage statistics
- Aggregated yield estimates
- Peer benchmarking data for farmer comparison

### 2.5 Consent APIs
**Used by**: Orchestrator, Frontend (Mobile + Web)

Enable the capture, management, and verification of **farmer consent**:
- Consent request creation and tracking
- Granular field-level consent (demographics, assets, crop data)
- Consent revocation workflows
- e-Sign integration (Aadhaar OTP)

### 2.6 Network Manager APIs
**Used by**: API Gateway (Kong), Auth Layer

Facilitate authentication and authorization of entities within the AgriStack ecosystem:
- Entity registration and credential management
- Token-based authentication (OAuth2)
- Role-based access validation

### 2.7 Telemetry APIs
**Used by**: Monitoring Agent, Observability Stack

Monitor API usage, performance, and overall system health:
- Request/response latency tracking
- Error rate monitoring
- Quota and rate limit status

---

## 3. Step-by-Step: Browsing the API Catalogue

### Step 1: Open the Catalogue Page
- Navigate to the **API Catalogue** tab from the top menu
- The page displays all available API products as category cards

### Step 2: Search for APIs
- Type a keyword into the **"Search by keyword"** bar
- Click the **Search** icon
- Results filter based on the entered keyword

### Step 3: Switch View Layout
Toggle between two display formats:
- **Grid View** — Card-based visual layout
- **List View** — Compact table format

### Step 4: Browse Category Cards
Each category card shows:
- **Category Name** (e.g., Farmer Data APIs)
- **Number of APIs** inside the category
- **Short Description** of what the category covers

**Examples**:
- State APIs – 3 APIs
- Network Manager – 2 APIs

### Step 5: Open a Category
- Click any **category card** to view the list of APIs under that category
- A description of the selected category appears at the top

### Step 6: Explore API Details
Inside each category, click any API name to view:
- **Overview** — What the API does
- **Parameters** — Required and optional fields
- **Response Details** — Schema and sample response
- **Documentation** — Downloadable API specification

### Step 7: Download Documentation
- Click the **Documentation icon** (📄) in the API list table to instantly download the API spec

---

## 4. Step-by-Step: Testing APIs in the Sandbox

### Step 1: Select an API for Testing
- From any API category page, each API entry shows:
  - Name and HTTP method (`POST`)
  - Type and brief description
- Click the **View** button under the "Try It Now" column to open the API detail page

### Step 2: Open Sandbox Environment
- On the API detail page, click **"Test in Sandbox"**
- This navigates to the sandbox testing environment

### Step 3: Generate Access Token
Before testing any API, you must authenticate:

1. Navigate to the **IAM** section
2. Click on the **Token API**
3. Open **Try It Now** or **Test in Sandbox**
4. Enter your credentials:
   - **Username**: (received via email after registration approval)
   - **Password**: (received via email after registration approval)
5. Update the editable payload fields in the request body
6. Click **Run** to execute the request
7. Copy the returned **Access Token** from the response

### Step 4: Select Mapper
- Choose the appropriate mapper from the list
- Example: **Seek API with mapper ID `i1004:o1007`** (synthesized data available)

### Step 5: Configure and Send Request
1. The page displays the request body in **editable format**
2. Enter the **Access Token** in the header section:
   ```
   Authorization: Bearer <your_access_token>
   ```
3. Modify the request payload as needed
4. Click **Run** to send the request

### Step 6: View Response
- API response appears instantly below the request
- Check response status, data fields, and any error messages
- The page also displays **cURL commands** with export options in multiple languages

---

## 5. Consent Management Workflow

### 5.1 Accessing the Consent Manager (ACM Portal)

#### Step 1: Open ACM Portal
- After logging in, click **ACM** from the home page
- A new window opens with the ACM portal

#### Step 2: Select State
- Select your **State** from the dropdown list

#### Step 3: Log In with Farmer ID
- Enter the **Farmer ID** in the input field
  > ⚠️ For sandbox testing, the Farmer ID is provided in the note section below the field

#### Step 4: OTP Verification
- Enter the **Login OTP** on the OTP page
  > ⚠️ For sandbox testing, the default OTP is **`000000`**
- Click **Submit** to complete verification

---

### 5.2 Consent Manager Dashboard

After OTP login, the **Consent Manager Landing Page** displays:

#### Summary Cards
| Card | Description |
|---|---|
| Consent Count | Total consents issued |
| Active Consents | Currently active data-sharing consents |
| Pending Consents | Awaiting farmer action |
| Revoked Consents | Previously granted, now withdrawn |

#### Consent List Table

| Column | Description |
|---|---|
| Consent Requester | Entity that requested the consent |
| Consent Status | Active, Revoked, E-sign Awaited, etc. |
| Acted On | Date when consent was generated |
| Expires On | Consent expiry date |
| Purpose | Reason for which consent was requested |
| E-sign | Whether e-sign is completed or pending |
| Action | View Details / Revoke buttons |

---

### 5.3 Granting Consent

#### Step 1: Review Consent Request
Open the **Farmer Consent Form** and review:
- Requesting entity name
- Purpose of data request
- Validity date of consent

#### Step 2: Check Demographic Data
Verify which fields are being requested:
- Farmer Name, Date of Birth, Gender, Caste Category
- PAN details, PM KISAN ID, State LGD Code

Each field has a **toggle ON/OFF** icon to control sharing.

#### Step 3: Review Assets Data
Check asset-related data fields:
- **Crop Data** — Season-specific crop history
- **Land Data** — Geo-referenced parcel information

#### Step 4: Grant or Deny
- Click **Grant** — Approves the consent and shares selected data
- Click **Deny** — Rejects the consent request

#### Step 5: E-Sign Authentication
If granting consent:
1. Select authentication method: **Aadhaar Number**, **Virtual ID**, or **UID Token**
2. Enter identification details
3. Choose OTP method: **Aadhaar TOTP** or **Aadhaar OTP**
4. Click **Get OTP**
5. Enter the received OTP
6. Accept the Aadhaar authentication checkbox (mandatory)
7. Click **Submit** to complete e-sign

> ⚠️ In sandbox mode, use test Aadhaar credentials provided in the portal.

---

### 5.4 Revoking Consent

#### Step 1: Click Revoke
- From the consent list, click **Revoke** in the Action column

#### Step 2: Review Details
- The Farmer Consent Form opens showing all shared demographic and asset data

#### Step 3: Confirm Revocation
- A warning popup appears:
  > "Revoking consent may stop the services currently being received."
- Click **Revoke** to confirm withdrawal
- Click **Cancel** to keep consent active

After revocation, the consent status updates immediately in the dashboard.

---

## 6. Moving to Production

### Step 1: Request Production Access
- Click the **profile icon** → select **"Production Request"** from the menu
- The Move to Production form opens with some fields pre-filled

### Step 2: Provide Security Artifacts
| Artifact | Description |
|---|---|
| **Public Key** | Upload for encrypting production API calls |
| **Certificates** | Attach SSL or encryption certificates |
| **Endpoints** | Select API endpoints to move to production (must be sandbox-tested) |

### Step 3: Provide Additional Information
| Field | Description |
|---|---|
| **Expected Daily Volume** | Estimated daily API call count in production |
| **Integration Contact** | Technical person responsible for API integration |
| **Data Retention Policy** | Upload company's data retention document |
| **Escalation Contact** | Contact for production incident escalation |

### Step 4: Submit and Await Approval
- Review all details and submit the form
- The AgriStack team will review and approve the production migration request

---

## 7. SasyaAI Sandbox Integration Map

```
┌─────────────────────────────────────────────────────────────┐
│                    AgriStack Sandbox                         │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Farmer   │  │  Land    │  │  Crop    │  │ Consent   │  │
│  │ Data API │  │ Data API │  │ Data API │  │   APIs    │  │
│  └─────┬────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│        │            │             │               │         │
│  ┌─────┴────┐  ┌────┴─────┐  ┌───┴──────┐  ┌────┴──────┐  │
│  │Aggregated│  │ Network  │  │Telemetry │  │  Token    │  │
│  │ Data API │  │ Manager  │  │   API    │  │   API     │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ HTTPS (OAuth2 + Bearer Token)
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                      SasyaAI Platform                        │
│                                                              │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │ Orchestrator │  │ Planning Agent │  │ Geospatial Agent│  │
│  │  (Farmer     │  │ (Crop + Land   │  │  (Land Data +   │  │
│  │   Data API)  │  │  Data APIs)    │  │  Aggregated)    │  │
│  └──────────────┘  └────────────────┘  └─────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │ Monitoring   │  │ Consent Flow   │  │ Auth / Gateway  │  │
│  │  (Telemetry) │  │ (Consent APIs) │  │ (Network Mgr)   │  │
│  └──────────────┘  └────────────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 8. Sandbox Testing Checklist for SasyaAI

| # | Test Case | API Category | Status |
|---|---|---|---|
| 1 | Authenticate and obtain access token | Network Manager / Token API | ☐ |
| 2 | Fetch farmer demographic profile by Farmer ID | Farmer Data API | ☐ |
| 3 | Retrieve geo-referenced land parcel map | Land Data API | ☐ |
| 4 | Fetch season-specific crop data for a land record | Crop Data API | ☐ |
| 5 | Get village-level aggregated crop survey data | Aggregated Data API | ☐ |
| 6 | Create a consent request for farmer data access | Consent API | ☐ |
| 7 | Grant consent with e-Sign (test Aadhaar) | Consent API | ☐ |
| 8 | Revoke an active consent and verify status change | Consent API | ☐ |
| 9 | Monitor API call telemetry and latency | Telemetry API | ☐ |
| 10 | Simulate full Digital Twin creation pipeline | End-to-End | ☐ |
| 11 | Test rate limiting behavior at scale | Network Manager | ☐ |
| 12 | Validate error handling for invalid Farmer IDs | Farmer Data API | ☐ |

---

## 9. Sandbox Credentials & Access

> ⚠️ **Never commit sandbox credentials to version control.**

| Item | Location |
|---|---|
| Sandbox URL | [https://sandbox.agristack.gov.in/](https://sandbox.agristack.gov.in/) |
| Username / Password | Sent via email after registration approval |
| Test Farmer ID | Displayed on the sandbox login page (note section) |
| Test OTP | `000000` (sandbox only) |
| Access Token TTL | Short-lived; regenerate before each testing session |

Store sandbox credentials in `.env.local` (git-ignored) or HashiCorp Vault.
