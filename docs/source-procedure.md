# Source procedure: retrospective fixes

The predictor learns from a **fix list**: words the current ASR model is confirmed to get wrong for
this speaker, each with the wrong forms it wrote. This page records how that list is built in the
Hebrish project (procedure as of 2026-10-25), so the predictor's input is well defined. It is the
"retrospective" half of the loop: it only finds errors that have already happened.

## Steps

1. **Collect real transcription history.** The dictation app stores every transcript locally
   (Hebrish desktop 0.7.0+: a SQLite history). Each row carries the model's text, the model name and,
   from app 0.7.3, the exact weights revision and decode settings. When the speaker corrects a
   transcript in the app, the corrected text is stored and the model's text kept as `original`.
2. **Stage privately.** New rows (text only, no audio) are exported to a private dataset for
   analysis. Nothing from this stage is published.
3. **Read every new row and flag mishearings.** An agent reads each row and flags any word or phrase
   that reads as a mishearing of something the speaker plausibly said. Two automatic signals help but
   do not replace the read:
   - **corrections**: word-level `wrong → right` pairs from rows the speaker corrected (exact, but
     only as many as get corrected);
   - **suspects**: words in the model's text that are close to a known lexicon term but are neither
     that term nor English (automatic, noisy, and blind to most tech, name and plain-English errors).
4. **Scope: every kind of word.** Tech and brand names, acronyms, AI/ML terms, names of people,
   companies and projects, Hebrew and Yiddish terms (romanized), and ordinary English words heard as
   something else. **Not errors:** casing or punctuation alone, disfluencies the speaker really said,
   and spellings plausible for what was said. Unclear cases are marked "unsure" for the speaker.
5. **Group** by correct form: the wrong forms, their counts, and one occurrence per error (row id,
   model, revision, date).
6. **Speaker confirms.** The table (heard as → should be → count) goes to the speaker, who strikes
   rows. **The speaker's confirmation is the label.** Nothing unconfirmed is added.
7. **Promote.** Each confirmed word gets its correct form, `kinds` (tech, ai_interactions, linux,
   smart_home, personal, hebrew, yiddish, medical, drug, name, other), a short meaning, and its
   occurrences. It then goes to:
   - the capture app's **priority-word list**, which serves new generated sentences with that word
     first until it has 20 recorded takes, recording 1 in 5 of them as held-out test;
   - a private review log (per word: wrong forms and occurrences; no text);
   - the public error list, `Hebrish/ASR-Error-List`: word, wrong forms, model and version, date and
     training progress only.
8. **Test each release** against the list (the `errata-release-test` procedure): for each listed
   word, does the new release write it correctly on held-out recordings it never trained on, compared
   with the release before? Verdicts: fixed, still failing, regressed.

## What the predictor gets from this

| Field | Source | Use in the predictor |
|---|---|---|
| `word` | confirmed fix | positive example |
| `heard_as[]` | the ASR's wrong forms | aligned against `word` to extract the confusion (see `confusion-taxonomy.md`) |
| `kinds[]` | assigned at promotion | stratifying, and a feature |
| occurrences per model and revision | review log | whether a failure is persistent or one-off; per-version labels |
| words said and transcribed **correctly** | the same history | negative examples (see `training-plan.md`, "Labels") |
| per-release errata verdicts | errata test | whether training fixed it; how hard each pattern is to train away |

## Its limits, which motivate the predictor

- It finds only words the speaker has already said, in the contexts they happened to say them.
- It depends on the speaker noticing or correcting, and on an agent reading every row.
- Each word costs 20 recorded takes once confirmed, so it is worth knowing which unsaid words are
  likely to fail before recording for them.
