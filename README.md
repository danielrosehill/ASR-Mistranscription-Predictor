# ASR Mistranscription Predictor

**Status: plan only (2026-10-25).** No code, data or model yet.

A model that takes a list of words a speech recognition (ASR) model is known to get wrong for one
speaker, and predicts **other words that it will also get wrong** for that speaker, so they can be
recorded and added to a fine-tune before they ever show up as errors in real use.

## The problem

Fine-tuning an ASR model on your own voice usually starts reactively. You dictate, you notice
mistakes ("ROCm" written as "Rockham", "Qdrant" as "Qdrint", "LoRA" as "Laura"), you collect them
into a fix list, you record training sentences for those words, you retrain. That only ever fixes
words you have already said and already caught. The next failing word is found the same way, one
mistake at a time.

The fix list is not random, though. The errors share causes: the base model has never seen the word,
an acronym's letters blur into similar letter names, the word sounds like a more common English word
and gets snapped to it, the speaker's accent shifts a sound the model relies on. If those causes can
be identified from the confirmed fixes, they can be used to score words that have **not** failed yet,
because they have not been said yet.

## The idea in one loop

```
dictation history ──► retrospective fix list ──► pattern analysis ──► predictor
       ▲                 (confirmed errors)        (phonetic, lexical,      │
       │                                            orthographic)           ▼
       │                                                        candidate words scored
       │                                                        by P(mistranscribed)
       │                                                                    │
  fine-tune ◄── training sentences recorded ◄── probe: does the current ◄───┘
                for confirmed predictions        model really fail them?
```

1. **Retrospective fixes** (exists today): mine the speaker's real transcription history, find what
   the model got wrong, and have the speaker confirm a fix list of `correct word → wrong forms`.
   See [`docs/source-procedure.md`](docs/source-procedure.md).
2. **Pattern analysis**: explain each confirmed fix in terms of features that generalise (phoneme
   confusions, acronym structure, subword fragmentation, a frequent English neighbour, casing).
   See [`docs/confusion-taxonomy.md`](docs/confusion-taxonomy.md).
3. **Prediction**: score a pool of candidate words the speaker is likely to say by how likely the
   current model is to get them wrong.
4. **Probe**: check the top predictions against the real model (cheap synthetic probe first, then
   real recordings) before they cost any recording time in bulk.
5. **Train**: confirmed predictions join the fix list and get training sentences like any other fix.

The full plan (data, features, model options, evaluation, how predictions enter training) is in
[`docs/training-plan.md`](docs/training-plan.md). Undecided points are in
[`docs/open-questions.md`](docs/open-questions.md).

## Where this comes from

It was planned for the [Hebrish](https://hebrish.app) fine-tunes of `nvidia/parakeet-tdt-0.6b-v2`
(English with Hebrew code-switching, one speaker), whose retrospective fix list is published as the
Hugging Face dataset [`Hebrish/ASR-Error-List`](https://huggingface.co/datasets/Hebrish/ASR-Error-List)
(87 confirmed words as of 2026-10-25). The method is not tied to that project: any single-speaker
ASR fine-tune with a dictation history and a fix list can use it.

## Privacy

The input to step 1 is private dictation text. This repo, and anything published from it, holds
only the confirmed words and the wrong forms the ASR wrote, never a sentence or phrase of the
speaker's dictation.
