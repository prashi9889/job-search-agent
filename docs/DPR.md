# Detailed Project Report (DPR) — Personal Job Search Agent, v0.2

**Purpose:** This report defines what the agent should do, how it should work, what it may use, and what must be decided before implementation. v0.2 records the Phase 1 decisions (see [decisions.md](decisions.md)).

## 1. Project description

A personal, local-first assistant that helps you find jobs worldwide, compare them with your verified professional profile, prepare tailored application materials, assist with applications after your approval, and maintain a job-application tracker.

The system is for personal use on your computer. It may need an internet connection to find job listings and access services you later authorize. "Runs on my computer" does not automatically mean that every AI model or connected service processes data locally; see D2 in the decisions log for the agreed split.

## 2. Goals and requirements

The agent should:

- Search for jobs across locations worldwide, including remote and onsite roles, without a preferred location filter.
- Compare job descriptions with your verified education, experience, skills, and preferences.
- Explain matches, gaps, uncertainties, location requirements, and stated work-authorization requirements.
- Create a distinct, tailored resume for each role using only facts you have verified.
- Optionally prepare a tailored cover letter.
- Require your approval before submitting each application or sending any email.
- Check for duplicate applications before assisting with submission.
- Identify job-related Gmail messages such as confirmations, recruiter messages, assessments, interviews, rejections, and offers.
- Extract proposed dates and status changes for your review.
- Maintain an Excel tracker and an audit history of important actions and changes.
- Protect personal information, treat job listings and emails as untrusted content, and make errors or uncertain results visible.

**ATS requirement:** The agent should create readable, relevant resumes and align supported language with the job description. It cannot guarantee a particular ATS score, a "100% match," or an interview.

## 3. Scope

**Included:** job discovery, profile-based matching, per-role document drafts, approval-based application assistance, email-based application tracking, an Excel tracker, follow-up reminders, duplicate checks, and an audit history.

**Outside the initial scope:** automatic application submission without your approval; automatic outgoing emails; inventing or inferring qualifications as facts; and a shared or public service for other users.

## 4. How it works

1. **You provide and verify your profile.** The agent uses only details you review and approve.
2. **It finds and organizes job listings.** Listings are filtered and deduplicated, then ranked against your profile.
3. **It explains each match.** You can see supporting qualifications, gaps, and details that need checking.
4. **It prepares application materials.** A resume, and optionally a cover letter, is tailored to that role. Claims must be traceable to your verified profile.
5. **You review and approve.** The agent waits for your decision before application submission.
6. **It records the application.** The tracker stores the job details, date, source, account used, and resume version.
7. **It monitors authorized email.** The agent proposes updates based on relevant messages; you review dates and status changes.
8. **It tracks next steps.** The dashboard and tracker show the current stage, interview dates, next action, and notes.

## 5. Architecture and information flow

```text
Job sources ─► Discovery and duplicate check ─► Job shortlist
                                                    │
Verified profile ─► Matching and gap analysis ─► Draft materials
                                                    │
                                              Your approval
                                                    │
                                       Application assistance
                                                    │
Gmail, if authorized ─► Proposed email updates ─► Your review
                                                    │
                                Local workbook + audit history
```

**Main parts:**

- **Local agent and dashboard:** Python + FastAPI on `127.0.0.1`. Shows jobs, drafts awaiting review, application stages, errors, and next steps.
- **Privacy router:** Decides, for every model call, whether the data may leave the machine (`jobagent/privacy.py`).
- **Profile store:** Holds your approved personal, education, work-history, and skills information.
- **Job collection and matching:** Reads selected job sources and compares listing requirements with profile facts.
- **Document preparation:** Creates tailored resume and optional cover-letter versions.
- **Approval queue:** Presents the job, match explanation, draft materials, and pending action.
- **Email reader:** Uses Gmail only after you authorize it. Read-only access is the starting permission.
- **Tracker:** A local Excel workbook by default. Microsoft 365 can be connected later if you explicitly choose it.
- **Audit history:** Append-only SQLite log of approvals, document versions, status changes, sync results, privacy events, and corrections.

## 6. What the system uses

| Capability | Decision | Requires your authorization |
|---|---|---|
| Running the agent | Your computer, `~/.jobagent` data directory | Done (Phase 1) |
| Job tracking | A local Excel workbook you select | Permission to access that workbook |
| Microsoft 365 | Optional later connection | Separate authorization and sign-in |
| Gmail | Optional, read-only monitoring | Gmail authorization |
| Job listings | Sources you select | Approval of sources and access method |
| AI model | **Hybrid:** local model (Ollama) for all personal data; Claude API for public job-listing text only, after opt-in | `jobagent privacy --external-opt-in on` |

## 7. Tracker fields and stages

**Fields:** company, role, job link, application date, sender/from email, source, resume version, email outcome or sentiment, current stage, interview dates, next action, and notes.

**Stages:**
`discovered → shortlisted → resume prepared → approved → applied → confirmation received → assessment/interview scheduled → interview completed → offer / rejected / withdrawn`

The system also records when a proposed update was reviewed or corrected, so the tracker can be audited.

## 8. Privacy and safety requirements

- Keep profile details, drafts, the workbook, and audit history on your computer by default.
- Do not connect Gmail, Microsoft 365, job sources, or inspect local workbooks until you authorize the specific access.
- Store account credentials through secure operating-system or provider mechanisms; never place them in the tracker or resume.
- Treat job descriptions and email contents as data to analyze, not instructions for the agent to follow.
- Ask before applying or sending messages.
- Check for likely duplicates before progressing an application.
- Make it possible to review, correct, and delete profile data and generated drafts.
- Clearly show when information is missing, uncertain, or based on an automated interpretation.

## 9. Phased implementation plan

| Phase | Deliverable | Review point |
|---|---|---|
| **1. Project setup and privacy choice** | Local project and dashboard; hybrid AI routing | Approve storage and processing approach |
| **2. Profile and preferences** | Verified professional profile and job-search criteria | Review every stored fact and preference |
| **3. Tracker** | Local workbook structure, stages, duplicate rules, and audit history | Review columns and sample records |
| **4. Job discovery and matching** | Approved listing sources, worldwide search, matching explanations | Review sample results and ranking |
| **5. Tailored documents** | Resume and optional cover-letter drafts per role | Review claims and formatting |
| **6. Application assistance** | Approval queue and duplicate check | Confirm no submission occurs without approval |
| **7. Gmail monitoring** | Read-only email classification and proposed tracker updates | Review extracted messages and dates |
| **8. Ongoing operation** | Reminders, sync monitoring, backups, corrections, and maintenance | Review errors and recurring workflow |

## 10. Completion criteria

The system is ready for regular use when you can verify that it:

- Uses only profile facts you approved.
- Explains why a job matches and identifies meaningful gaps.
- Creates a role-specific resume with a recorded version.
- Stops for your approval before an application or outgoing email.
- Detects likely duplicate applications.
- Records tracker updates with dates and source context.
- Presents Gmail-derived updates for review.
- Keeps the agreed data on your computer and reports any external processing clearly.

## 11. Current dashboard

| Work area | Progress | Status |
|---|---:|---|
| Initial architecture and workflow | 100% | Defined |
| Personal, local-first operating preference | 100% | Recorded |
| Worldwide, remote and onsite search scope | 100% | Recorded |
| AI processing choice | 100% | Hybrid (D2) |
| Phase 1 project and dashboard | 100% | Built, awaiting your review |
| Verified professional profile | 0% | Not provided |
| Workbook selection and tracker approval | 0% | Not started |
| Integrations | 0% | Not authorized |
| Tests | — | 10 Phase 1 tests passing |
