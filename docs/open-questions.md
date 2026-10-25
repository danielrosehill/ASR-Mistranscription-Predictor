# Open questions

Decisions not yet made (2026-10-25). Update this file when one is settled, with the date and who
decided.

1. **Where the code lives.** Here, or as a step inside the existing history-review procedure? Plan:
   prototype here; once it runs per review, the review procedure calls it.
2. **Candidate pool sources.** Which glossaries count as "words the speaker is likely to say", and
   whether personal names from the speaker's context are in scope at all.
3. **Negative threshold.** How many correct occurrences make a word a negative (plan says 3).
4. **Synthetic probe trust.** Whether the voice-clone probe is good enough to skip real takes for
   words it confidently clears, or only to order the real probes. Decide after calibration (phase 3).
5. **Real-probe size.** 3 takes per candidate is a guess; the errata test's own rule is "fewer than
   3 clips: needs more takes, don't call it".
6. **Orthographic fixes.** Trained with recordings like the rest, or handled by text post-processing
   (casing and stylised names) and kept out of the acoustic predictor?
7. **Per model line.** Hebrish has several model lines (Sabich, Jachnun, Shakshuka) on different
   bases. One predictor across lines with a line feature, or one per line?
8. **Publishing the predictions.** Whether the ranked candidates (single words only) are published
   alongside the public error list, marked as predicted.
