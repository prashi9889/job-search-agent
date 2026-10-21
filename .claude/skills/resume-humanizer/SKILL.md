---
name: resume-humanizer
description: Rewrite resume, cover-letter or application text so it reads as written by the candidate, in plain specific language with no stock AI phrasing. Use whenever a resume or cover letter is drafted or tailored for a job.
---

# Resume humanizer

Goal: the text should sound like a real person describing their own work.
It must stay truthful. Never add, inflate or invent facts; only use facts from
the verified profile (`~/.jobagent/profile.json`).

## Rules

1. **Plain verbs.** Prepared, checked, measured, took off, recorded, followed
   up, planned. Not spearheaded, leveraged, orchestrated, utilised.
2. **Specific over impressive.** "Checked contractor bills against completed
   work before payment" beats "ensured financial accuracy across projects".
3. **No filler adjectives.** Drop dynamic, results-driven, highly motivated,
   detail-oriented, passionate, proven track record, seamless, robust.
4. **Vary sentence openings.** No more than two bullets in a row starting with
   the same verb. Mix short and medium bullets.
5. **One idea per bullet, under ~25 words.** Split long sentences.
6. **No em dashes, no semicolon chains,** no rhetorical questions, no
   "In today's fast-paced world".
7. **Industry words are fine** when they are the real terms of the job
   (BOQ, rate analysis, NRM2, take-off, IS 1200). Use the candidate's own
   phrasing from their messages where possible.
8. **Keep the candidate's level honest.** A fresher "assisted", "prepared",
   "learned"; does not "managed a portfolio" or "led teams".
9. **Regional spelling:** UK/Gulf/India resumes use British spelling
   (organised, programme, metre).

## Check

After writing, run:

```bash
jobagent humanize path/to/resume.docx
```

Fix every finding, then run it again until it reports nothing. Then read the
whole resume aloud once: anything you would not say in an interview gets
rewritten.

Note: no tool can guarantee a "100% human" score on every AI detector. These
rules remove the patterns detectors and recruiters most often flag.
