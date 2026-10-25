---
license: cc-by-4.0
language:
- en
- he
pretty_name: ASR Error Prediction (Hebrish)
tags:
- asr
- speech-recognition
- error-prediction
- code-switching
- fine-tuning
- hebrish
task_categories:
- text-classification
size_categories:
- 1K<n<10K
---

# ASR Error Prediction

Training data for a model that predicts **which words a speech recognition model will get wrong for
one speaker**, by extrapolating from the words it has already been confirmed to get wrong. Built for
the [Hebrish](https://hebrish.app) fine-tunes of `nvidia/parakeet-tdt-0.6b-v2` (English with
romanized Hebrew code-switching). Plan, scripts and method:
[danielrosehill/ASR-Mistranscription-Predictor](https://github.com/danielrosehill/ASR-Mistranscription-Predictor).

## Segments

Every config is split by **segment**, so predictions can be made and used per training dataset:

| Segment | What it covers | Source of candidates |
|---|---|---|
| `codeswitching` | romanized Hebrew and Yiddish terms | the Hebrish lexicon (places, food, bureaucracy, religious life, ...) |
| `tech` | tech, AI, Linux and smart-home terms and acronyms | the project's tech vocabulary packs, plus LLM proposals |
| `names` | people, companies, projects | none yet (fixes only) |
| `general_english` | ordinary English words | LLM proposals |

<!-- counts -->

## Configs

- **`fixes`**: the positives. Words confirmed wrong in the speaker's real dictation, from
  [`Hebrish/ASR-Error-List`](https://huggingface.co/datasets/Hebrish/ASR-Error-List) (pinned in
  `error_list_rev`): `word`, `heard_as` (the wrong forms the ASR wrote), `kinds`, `occurrences`,
  `models`, dates, and `label` (`acoustic`, or `orthographic` when the only error is casing or a
  hyphen).
- **`candidates`**: words the speaker is likely to say that are not on the fix list: `term`,
  `domain`, `meaning`, `takes` (recorded training takes so far; null = unknown) and `pool` (source
  file and commit).
- **`predictions-<run>`**: one model's scores for the candidates, plus terms it proposed outside the
  pools (`origin`: `pool` or `proposed`): `p_fail` (0-100), `pattern` (the confusion class it
  applied), `likely_heard_as`, `reason`, `rank` within the segment.

**Predictions are not labels.** They are rankings to be checked against the real model (a synthetic
probe, then a few real recordings) before any word gets training sentences. Confirmed ones move to
the error list with `source: predicted`.

## Runs

| Run | Date | Model | Notes |
|---|---|---|---|
| `haiku-r1` | 2026-10-25 | `claude-haiku-5-5` (Anthropic Batch API, low effort; batch `msgbatch_01SFKjYbEtvGqChr8eo3JXPk`, US$0.13) | first pass; fix list at 87 words; scores every candidate in chunks of 60 with the whole fix list as evidence, plus 52 proposed tech terms and 55 proposed English words; 1 candidate missing from the replies |

**`haiku-r1` caveats.** Scores are uncalibrated and not comparable across segments. Code-switching
scores run high (mean 58 for terms with no recorded takes, 37% of candidates at 60 or above) because
the fix list has only 7 Hebrew words to learn from, so Haiku leans on "Hebrew = hard". Scores do
fall with recorded takes (mean 58 at 0 takes, 49 at 1 to 4, 31 at 5 to 19, 22 at 20 or more), which
is the expected direction. Use ranks within a segment, not thresholds. Wrong forms that equalled
the term itself (1,175 of them) were removed after the run.

## Not included

No audio, and nothing from the speaker's dictations beyond single confirmed words and the ASR's
wrong forms. Negatives (rare words the model transcribed correctly) are planned but not published
yet.
