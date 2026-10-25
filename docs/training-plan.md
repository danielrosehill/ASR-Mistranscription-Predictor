# Training plan

Goal: given the current ASR model and a speaker's confirmed fix list, rank words the speaker is
likely to say by the probability the model will mistranscribe them, so the top of the ranking can be
recorded and trained on before the errors happen.

Success is practical: **of the words the predictor puts in its top k, what fraction does the current
model really get wrong for this speaker**, compared with picking k words at random from the same
candidate pool. If it cannot beat that baseline clearly, the reactive loop alone is enough.

## 1. Data

### Positives

The confirmed fix list (`docs/source-procedure.md`): `word`, `heard_as[]`, `kinds[]`, occurrences per
model revision. 87 words on 2026-10-25, growing with each history review. Keep orthographic-only
fixes as a separate label (`docs/confusion-taxonomy.md`).

### Negatives

Words the speaker **said and the model wrote correctly**, from the same history: every word of a
reviewed row that was not flagged. This needs care:

- restrict to words that are rare enough to be informative (a word in the top few thousand English
  words is trivially correct and teaches nothing); match negatives to positives by frequency band and
  `kinds`;
- a word counts as negative only after N correct occurrences (start with N = 3), so one lucky
  transcription is not a label;
- negatives come out of private text but are single words, so they can be stored like the fix list.

### Candidate pool (what gets scored)

Words the speaker is **likely to say but has not said yet** (or not often):

- the project's lexicon of Hebrew terms not yet recorded (Hebrish `lexicon.json`);
- domain glossaries matching the speaker's topics: AI/ML, Linux, self-hosting, dev tools, Israeli
  institutions and places (each source logged with its URL and date);
- names from the speaker's own context (projects, tools in use, contacts' names only if the speaker
  opts in);
- new terms from the news or release notes in those domains (the Hebrish `news-vocab` procedure).

Words already on the fix list are excluded from scoring and used for evaluation only.

## 2. Features

Per word, computed from text alone (no audio needed to score a candidate):

| Group | Features |
|---|---|
| Phonetic | phoneme sequence (G2P: eSpeak NG, or CMUdict where present; Hebrew terms from the romanization); syllable count; presence of phoneme contexts that appear in this speaker's confirmed confusions (see "Pattern extraction") |
| Neighbourhood | phonetic edit distance to the nearest much-more-frequent English word, and that word's frequency ratio (the snap-to-neighbour signal) |
| Lexical | corpus frequency (English web, and the base model's training text if known); in or out of a standard English dictionary; origin (English, Hebrew, brand/coinage) |
| Tokenizer | number of subword pieces under the ASR model's own tokenizer (Parakeet v2: 1,024-piece SentencePiece); whether the canonical spelling is reachable at all (no Hebrew characters in v2) |
| Orthographic | initialism or not; letter-name confusability score for initialisms; non-standard casing; hyphens or dots; compound of English parts |
| Kind | `kinds` from the fix list taxonomy |

### Pattern extraction from the fix list

For each confirmed fix, align the phonemes of `word` against each `heard_as` (weighted Levenshtein
over phonemes) and record the edit operations with one phoneme of context on each side, e.g.
`#[ə]m → #∅m` (initial drop), `[p] → [b]` in letter names, `[ɒk]` contexts. Count each pattern
across the list, weighted by how many distinct words show it (not by occurrences, so one word said
fifty times does not dominate). Patterns seen in at least two distinct words become features; each
candidate gets a count of the patterns its phoneme string could trigger.

## 3. Models, in order of cost

Build them in this order and stop when one is good enough.

1. **Rule baseline.** Score = weighted sum of: out-of-dictionary, subword count, nearest-neighbour
   snap risk, confusable-initialism, matched speaker patterns. Weights set by hand from the
   taxonomy. Needs no training; it is the bar the others must beat.
2. **Small classifier.** Logistic regression or gradient-boosted trees on the features above,
   positives vs frequency-matched negatives. Interpretable (feature weights say which patterns
   matter for this speaker), trains in seconds, fine at a few hundred labels.
3. **LLM extrapolation.** Give a model the fix list, the extracted patterns and a candidate pool,
   and ask it to rank candidates and name the pattern behind each. Useful for candidates where G2P
   is weak (brands, mixed-script names) and for proposing candidates outside the pool. Its output is
   a ranking to be probed, never a label.
4. **Learned confusion model (later, only with much more data).** A model of `P(heard_as | word,
   speaker)` over phoneme sequences, trained on fixes from several releases, that could also
   generate the likely wrong forms. Not worth it below a few hundred confirmed fixes.

## 4. Probing predictions before recording

A prediction costs recording time only once it is confirmed. Two probes, cheapest first:

1. **Synthetic probe.** Synthesize short sentences with the candidate in a clone of the speaker's
   voice (Hebrish has one: the Meorav TTS line), run them through the current ASR model, and check
   whether the word comes out right. Fast and free on CPU, but the clone may not reproduce the
   speaker's accent-specific confusions, so a pass here is weak evidence and a failure is strong
   evidence. Calibrate it first: run the probe on known fixes and known negatives and measure how
   well it agrees with them.
2. **Real probe.** A candidate that survives the synthetic probe (or the top k regardless) gets a
   few real takes (start with 3) through the capture app as test-split recordings, scored by the
   errata test against the current release. Fails → confirmed prediction; passes → negative label.

## 5. Into training

- Confirmed predictions join the fix list with `source: predicted` (kept distinct from
  `source: dictation` so their effect can be measured) and the priority-word list at its normal
  target (20 takes, 1 in 5 as test).
- Unconfirmed predictions are not trained on. A word that the model already gets right does not
  need recordings, and a sentence bank full of unnecessary words dilutes the training mix.
- Generated sentences follow the host project's dataset rules (for Hebrish: short sentences, one
  target term, code-switching and tech never in the same sentence, numbers in digits).
- Every probe result, positive or negative, is fed back as a label for the next predictor run.

## 6. Evaluation

- **Time split (main offline test).** Train on fixes confirmed before a cutoff date; score the pool;
  check how many words confirmed **after** the cutoff appear in the top k. This is the honest test
  of "predicting unknown fixes", because those words were unknown at the cutoff. Report
  precision@k and recall@k for k = 10, 25, 50, against the random-pool baseline and the rule
  baseline.
- **Prospective hit rate (the real test).** Of the top k predictions sent to the real probe, the
  fraction that fail. Compare with k random candidates probed the same way (needed once, to know the
  base rate of failure in the pool).
- **Downstream.** After a retrain that includes confirmed predictions, the errata test on those words
  (fixed / still failing / regressed) and the release's general WER, to check the extra words did
  not cost accuracy elsewhere.
- **Small numbers.** With tens of words per test, one word is an anecdote. Report counts alongside
  rates and do not call a difference from fewer than about 10 probed words per arm.

## 7. Phases

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | Export of the fix list and negatives as one table (public fields only) | table with positives, negatives, features stubbed. **Positives and candidate pools done 2026-10-25** (`Hebrish/ASR-Error-Prediction`, split by segment); negatives not yet |
| 0b | LLM extrapolation (model option 3) per segment | **`haiku-r1` done 2026-10-25**: every candidate scored, plus open proposals for `tech` and `general_english` |
| 1 | Features + pattern extraction script | every listed word has its alignment and pattern counts |
| 2 | Rule baseline and classifier, time-split evaluation | precision@k vs random reported |
| 3 | Synthetic probe, calibrated on known fixes | agreement with known labels measured |
| 4 | First prospective round: top k probed with real takes | hit rate vs random reported |
| 5 | Confirmed predictions in a release; errata test | downstream verdicts reported |
| 6 | Run per history review, as a step after the retrospective fix list | part of the routine loop |

## 8. Risks

- **Label bias.** The fix list contains what the speaker noticed and corrected; quiet errors in
  long dictations are under-represented, so the predictor may learn "what gets noticed".
- **Feedback loop.** Training on predicted words changes the model the predictor was describing;
  patterns must be re-extracted per release, and old fixes that are now fixed relabelled.
- **Small data.** Under ~100 positives the classifier will overfit; the rule baseline and the probe
  carry the weight until then.
- **Synthetic-probe mismatch.** A voice clone may smooth over exactly the accent features that cause
  speaker-specific errors.
