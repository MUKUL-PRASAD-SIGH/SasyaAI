# SasyaAI Demo Recording Guide

This guide is for a reviewer-facing demo of the local, synthetic SasyaAI
runtime. Record separate clips first and assemble the final video later. Keep
the browser at 1080p when possible, use a clean browser profile, and do not
show `.env`, API keys, real farmer data, terminal secrets, or model weights.

## Target video

- **Master cut:** 4 to 6 minutes
- **Short cut:** 60 to 90 seconds
- **Recording format:** 16:9, 1080p, 30 fps, MP4, system audio off unless needed
- **Screen capture:** browser only for the product story; use terminal capture
  only for the final health check
- **Voice:** record narration separately when possible so edits are easy
- **Evidence rule:** show the UI result and say that the corpus is synthetic

## Before recording

1. Start Docker Desktop and wait until the Linux engine is ready.
2. From the repository root, run `Copy-Item .env.example .env` if `.env` is
   missing, then run `docker compose up --build`.
3. Confirm `http://127.0.0.1:5174` and `http://127.0.0.1:5174/health` load.
4. Use the demo credentials in `REVIEWER_CREDENTIALS.md` or the README. Never
   put credentials on screen in the final cut.
5. Reset the demo state if a previous run makes the queue or history confusing.
6. Prepare three scenarios from the dashboard: **Crop plan · expected
   delivery**, **Leaf spots · review needed**, and **Aphid dose · blocked**.
7. Optional: prepare one harmless crop image for the Images/upload clip. Use a
   synthetic or non-identifying image only.

## Clip checklist

Use one file per row. Leave 2 seconds of quiet before and after each take.

| ID | Duration | Screen action | Spoken script / caption |
|---|---:|---|---|
| C01 | 15 sec | Show the sign-in screen and the three roles, then sign in as Farmer. | “SasyaAI is a safety-gated agricultural advisory demonstrator. Access is role-based, and this demo uses synthetic data.” |
| C02 | 20 sec | Open **Register new farmer**, show the form briefly, fill synthetic values, and enter the Farmer desk. | “A new farmer can create a scoped profile and enter the farmer desk without exposing another farmer’s records.” |
| C03 | 25 sec | In the advisory view, show the farmer profile, scenario selector, and query. Do not linger on personal-looking fields. | “The farmer asks a crop-planning question in the selected language. An optional crop image can be attached as evidence.” |
| C04 | 35 sec | Click **Run advisory workflow** for **Crop plan · expected delivery**. Show the result, verification checks, evidence, and status **Delivered after checks**. | “The answer is delivered only after evidence and deterministic checks for water, finance, weather, scheme, and dose. The language model is not the source of truth.” |
| C05 | 25 sec | Open **Agents** or the workflow view. Scroll through the agent-run cards and timeline. | “The workflow is observable: routing, specialist work, evidence retrieval, reflection, and safety verification are visible to the reviewer.” |
| C06 | 30 sec | Upload the synthetic crop image from **Images** or the advisory flow. Show the scan result and backend label. | “Crop images are processed through the available vision path. With no specialist weights, the demonstrator clearly falls back to pixel CV.” |
| C07 | 35 sec | Run **Leaf spots · review needed**. Show **Awaiting human review**, then open **HITL queue**. | “Low-confidence diagnosis does not auto-deliver. It creates a durable human-review case with the draft, evidence, checks, and trace.” |
| C08 | 35 sec | As Extension Officer, open the case, show the review context, add a short note, and use **Edit and approve** only if the UI permits it. | “An extension officer sees only the assigned scope, can review the evidence, and records an attributed decision.” |
| C09 | 25 sec | Run **Aphid dose · blocked**. Show the failed safety check and the review form with only **Reject draft**. | “A hard pesticide-safety failure cannot be overridden by human approval. The safe behavior is rejection and a new request with safe parameters.” |
| C10 | 20 sec | Sign in as Officer and show **Assigned farmers** and **HITL queue**. Avoid showing unnecessary IDs. | “Officer access is region-scoped. System administrators have broader runtime and audit visibility.” |
| C11 | 20 sec | Sign in as System Admin and show **Runtime**, **Metrics**, or **Audit**. Blur or crop sensitive-looking values. | “Operational views expose runtime health, metrics, and audit metadata for review.” |
| C12 | 15 sec | Show `/health` or the runtime panel, then end on the dashboard. | “This is a local demonstrator over synthetic seed data. Production integrations require separate approval and configuration.” |

## Recommended master edit

1. C01–C03: context and farmer entry, about 55 seconds.
2. C04–C06: normal advisory and observable AI workflow, about 1 minute 25 seconds.
3. C07–C09: the safety story, about 1 minute 35 seconds. This is the core of
   the demo and should receive the most screen time.
4. C10–C12: role boundaries, operations, and disclaimer, about 55 seconds.
5. Add a 3-second title card: **SasyaAI | Safety-gated agricultural advisory**.
6. Add small lower-third captions: **Synthetic demo data**, **Human review
   required**, and **Hard safety block** at the relevant moments.
7. Cut loading time, typing mistakes, duplicate clicks, and any credential or
   personal-looking data. Use hard cuts or short dissolves; do not add flashy
   AI effects over safety decisions.

## Short-video edit

Use C01 for 5 seconds, C04 for 20 seconds, C05 for 10 seconds, C07 for 15
seconds, C09 for 15 seconds, and C12 for 5 seconds. Put these captions on
screen in order: **Ask**, **Verify**, **Observe**, **Escalate**, **Block**,
**Review safely**.

## Hardware footage to record

Record these as separate 5–10 second clips. Keep the product dashboard as the
main visual; hardware footage is supporting context, not proof of live field
integration.

- `H01_device_wide.mp4`: phone or laptop running the dashboard.
- `H02_farmer_capture.mp4`: a synthetic crop image being captured or selected.
- `H03_connectivity.mp4`: device and network setup, with no passwords visible.
- `H04_reviewer_desk.mp4`: officer reviewing a case on a second screen.
- `H05_optional_sensor.mp4`: any available camera or sensor hardware, clearly
  labelled **concept footage** unless it is connected to this build.

Hardware narration: “The interface is designed for field-facing workflows,
but this recording shows the local demonstrator. The hardware shown here is
supporting or concept footage unless explicitly connected during the test.”

## AI video generation prompt

Paste this into the chosen video tool and replace the bracketed fields. Do not
ask it to invent product results, farmer identities, or live integrations.

> Create a 6–8 second realistic documentary-style establishing shot of a
> small Indian farm in [state/region], early morning, a farmer inspecting a
> healthy crop leaf with a phone, warm natural light, respectful and grounded,
> no visible brand logos, no readable personal data, no medical or pesticide
> claims, no text generated inside the scene. The farmer is preparing to use a
> safety-gated agricultural advisory dashboard. Camera movement is slow and
> stable, composition leaves clean space on the left for a title overlay.
> Label this as illustrative footage, not a live product result.

AI-video settings to record: tool name, model/version, prompt, seed if
available, aspect ratio, duration, generation date, and whether the clip was
edited or upscaled. Store that information with the source clip.

## Voice-over recording sheet

Record each line as a separate take and name it `VO_C01.wav`, `VO_C02.wav`, and
so on. Read at a calm pace, roughly 130–150 words per minute. The scripts in
the clip checklist are the default lines. Notes or alternate wording:

- Opening: ________________________________________________________________
- Normal delivery: _______________________________________________________
- Agent workflow: _______________________________________________________
- Human review: _________________________________________________________
- Hard block: ____________________________________________________________
- Closing disclaimer: ___________________________________________________

## Edit log and provenance

| Asset | Filename | Source / prompt | Duration | Used in cut | Notes |
|---|---|---|---:|---|---|
| Screen clip |  |  |  |  |  |
| Voice-over |  |  |  |  |  |
| Hardware clip |  |  |  |  |  |
| AI-generated clip |  |  |  |  |  |
| Music / SFX |  |  |  |  |  |

Final disclosure: **SasyaAI shown here is a local demonstrator using synthetic
seed data. AI-generated or hardware footage is labelled where applicable.
This video does not constitute agricultural, pesticide, or production advice.**
