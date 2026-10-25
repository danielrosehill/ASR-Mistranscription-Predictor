# Confusion taxonomy (first pass)

A first reading of the 87 confirmed words on `Hebrish/ASR-Error-List` (2026-10-25; model lines
Sabich, Jachnun and Shakshuka, all fine-tunes of English ASR bases). The classes are hypotheses for
the predictor's features, not a validated scheme: a word can sit in several classes, and the classes
have not been checked against any phonetic alignment yet.

| Class | What happens | Examples (correct → heard as) | Predictive signal for an unseen word |
|---|---|---|---|
| **Snap to a frequent English neighbour** | The model replaces a rare word with a common word one or two sounds away | prosody → porosity, Kaizen → Kaiser, agentic → agenda, skill → scale, Opus → Focus, evals → valves, Jupyter → Jupiter, Claude → clawed, subscription → prescription, marking → marketing | small phonetic edit distance to a much more frequent English word |
| **Acronym letter confusion** | Letter names that differ in one feature get swapped | APK → ABK, TTS → CTS, ASR → ACR, SSE → SSC, DMARC → GMARC | initialism containing confusable letter names (P/B, T/C/E, S/C, D/G) |
| **Initial segment dropped** | The first sound or letter is lost, often a vowel or a weak onset | AMD → MD, populated → opulated, remote → ote, Netanyahu → Etanyahu | word-initial vowel or letter-name vowel; possibly segmentation at utterance start |
| **Wrong word boundary** | One word split into two, or spelled as a phrase | Unsloth → On Sloth, NocoDB → No CodeDB, Cloudflare → cloud fair, Kdenlive → Caden Live | compound or brand built from English parts |
| **Novel coinage / out-of-vocabulary** | A new brand or term the base model never saw is spelled phonetically | Qdrant → Qdrint, Typst → TIPS-type, Ollama → ulama, Infisical → Infiniscal, Nemotron → Nematron | absent from the base training corpus; heavy subword fragmentation |
| **Acronym read as a word, or a word as an acronym** | The model picks the wrong reading | LLM → nelam, ONNX → onyx, regex → RedJack | letter string pronounceable as a word, or pronounced as one |
| **Consonant shift** | One consonant feature changes (voicing, place, manner) | repo → Refo, vocab → Rocab, Chatterbox → Shatterbox, few-shot → fusil | contains the consonant contexts seen shifting for this speaker |
| **Hebrew sounds** | Sounds or spellings outside English: /χ/, /ts/, Hebrew vowel patterns | Sabich → Tzabich, Hagihon → Gichon, Bituach Leumi → betuachlomi, Bezeq → Bezek | Hebrew origin; romanization conventions the base model has not seen |
| **Orthographic only** | Heard right, written wrong: casing, hyphen, stylisation | ROCm → ROCM, eSpeak → Espeak, F-Droid → FDroid | non-standard casing or punctuation in the canonical form |

## Notes

- **Orthographic errors are a different problem.** They are not acoustic and might be fixed with
  text-side post-processing rather than recordings. Keep them as a separate label so they do not
  teach the acoustic predictor that ROCm "sounds hard". (The source procedure excludes "casing
  alone" in general, but keeps it for canonical stylised names, hence their presence on the list.)
- **Speaker-specific vs model-generic.** Some classes (snap-to-neighbour, novel coinage) would hit
  any speaker; others (consonant shifts, initial drops) may be this speaker's accent or microphone.
  Separating the two matters: a generic error is predictable from text alone, a speaker-specific
  one needs features learned from this speaker's fixes.
- **Partly fixed already.** Some listed words may now pass after training. The errata verdicts tell
  which classes training removes easily and which persist; that is itself useful for prioritising.
