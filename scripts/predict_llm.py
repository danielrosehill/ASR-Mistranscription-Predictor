#!/usr/bin/env python3
"""LLM extrapolation (training-plan.md, model option 3): score candidates by P(mistranscribed).

Reads data/fixes.jsonl and data/candidates.jsonl (build_inputs.py) and sends one Anthropic batch:
  score     every candidate, in chunks of --chunk, with the whole fix list as evidence
  propose   open proposals for segments without a pool (general_english, and extra tech terms)
Writes data/predictions/<run>.jsonl: one row per scored or proposed term with `segment`, `p_fail`
(0-100), `pattern` (a confusion-taxonomy.md class), `likely_heard_as`, `reason`, `origin`
(pool | proposed) and `rank` within its segment. These are rankings to be probed, never labels.

The batch goes through ASR-Training's scripts/anthropic_batch.py (Daniel's LLM gateway, Haiku
by default, cost logged to ASR-Training/data/llm-usage.jsonl), imported from --asr-training.

Usage: uv run --with anthropic python scripts/predict_llm.py --run haiku-r1
       ... --resume msgbatch_...   collect an earlier batch instead of submitting again
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = ["snap_to_neighbour", "acronym_letters", "initial_drop", "word_boundary", "novel_coinage",
            "acronym_vs_word", "consonant_shift", "hebrew_sounds", "orthographic", "none"]
SYSTEM = """You predict which words a speech recognition model will mistranscribe for one speaker.

The model: fine-tunes of nvidia/parakeet-tdt-0.6b-v2, an English ASR model with an English-only
1,024-piece tokenizer. Hebrew and Yiddish words are written romanized. The fine-tunes were trained
on read sentences by this speaker covering code-switching (English with Hebrew terms) and some tech
vocabulary. A candidate with `takes` > 0 already has that many recorded training takes, which lowers
its risk; `takes` null means unknown.

The evidence: the speaker's confirmed fix list, words the current model got wrong in their real
dictation, each with the wrong forms it wrote. Infer from it which kinds of words fail and how
(the phonetic and orthographic patterns), then apply those patterns to the candidates.

Pattern classes:
- snap_to_neighbour: replaced by a more frequent English word a sound or two away (prosody -> porosity)
- acronym_letters: letter names confused (APK -> ABK, TTS -> CTS)
- initial_drop: first sound or letter lost (AMD -> MD, remote -> ote)
- word_boundary: split or merged wrongly (Unsloth -> On Sloth)
- novel_coinage: a new brand or term spelled phonetically (Qdrant -> Qdrint)
- acronym_vs_word: acronym read as a word or the reverse (LLM -> nelam, ONNX -> onyx)
- consonant_shift: one consonant changes (repo -> Refo, Chatterbox -> Shatterbox)
- hebrew_sounds: Hebrew sounds or romanization (Sabich -> Tzabich, Bezeq -> Bezek)
- orthographic: heard right, cased or punctuated wrong (eSpeak -> Espeak)
- none: no pattern applies; low risk

p_fail is your probability (0-100) that the current model writes the term wrongly when this speaker
says it in a sentence. Be calibrated: most ordinary words are low; reserve high values for terms
that share a pattern with several confirmed fixes. likely_heard_as: up to 3 wrong forms it would
most likely write (empty if p_fail < 20). reason: one short clause naming the evidence."""

ITEM = {"type": "object", "additionalProperties": False,
        "required": ["term", "p_fail", "pattern", "likely_heard_as", "reason"],
        "properties": {"term": {"type": "string"}, "p_fail": {"type": "integer"},
                       "pattern": {"type": "string", "enum": PATTERNS},
                       "likely_heard_as": {"type": "array", "items": {"type": "string"}},
                       "reason": {"type": "string"}}}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["predictions"],
          "properties": {"predictions": {"type": "array", "items": ITEM}}}
PROPOSE = {
    "general_english": "Propose 60 ordinary English words or short phrases (not names, not tech, "
                       "not Hebrew) this speaker plausibly says in everyday dictation and that the "
                       "model is likely to mistranscribe, following the patterns in the fix list.",
    "tech": "Propose 60 tech, AI, Linux or developer terms (tools, products, acronyms) that this "
            "speaker plausibly says, given the fix list's subjects, and that the model is likely to "
            "mistranscribe. Do not repeat any term from the fix list or the existing pool below.",
}


def load(name):
    return [json.loads(l) for l in (ROOT / f"data/{name}.jsonl").read_text().splitlines() if l.strip()]


def evidence(fixes):
    lines = [f"- {f['word']} [{f['segment']}; {', '.join(f['kinds'])}] heard as: "
             f"{' | '.join(f['heard_as'])} ({f['occurrences']}x)" for f in fixes]
    return "Confirmed fix list (correct -> wrong forms):\n" + "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", required=True, help="run name, e.g. haiku-r1")
    ap.add_argument("--chunk", type=int, default=60)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--asr-training", default=str(ROOT.parent / "ASR-Training"))
    ap.add_argument("--resume")
    ap.add_argument("--dry-run", action="store_true", help="print request count and one request")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(a.asr_training) / "scripts"))

    fixes, cands = load("fixes"), load("candidates")
    ev = evidence(fixes)
    reqs, chunks = [], {}
    for seg in ("codeswitching", "tech"):
        pool = [c for c in cands if c["segment"] == seg]
        for i in range(0, len(pool), a.chunk):
            part = pool[i:i + a.chunk]
            rid = f"score-{seg}-{i // a.chunk:03d}"
            chunks[rid] = part
            items = "\n".join(f"- {c['term']} (domain: {c['domain']}; takes: {c['takes']}; "
                              f"{c['meaning'] or ''})" for c in part)
            reqs.append({"id": rid, "system": SYSTEM, "schema": SCHEMA,
                         "user": f"{ev}\n\nScore every one of these {len(part)} {seg} candidates, "
                                 f"returning the term exactly as written:\n{items}"})
    tech_pool = ", ".join(c["term"] for c in cands if c["segment"] == "tech")
    for seg, ask in PROPOSE.items():
        extra = f"\n\nExisting tech pool (do not repeat): {tech_pool}" if seg == "tech" else ""
        reqs.append({"id": f"propose-{seg}", "system": SYSTEM, "schema": SCHEMA,
                     "user": f"{ev}\n\n{ask}{extra}"})
    if a.dry_run:
        print(json.dumps({"requests": len(reqs), "example": reqs[0]["user"][-1500:]}, indent=1))
        return

    from anthropic_batch import run_batch
    out = run_batch(reqs, stage=f"error-prediction-{a.run}", model=a.model, max_tokens=16000,
                    resume=a.resume)
    known = {f["word"].lower() for f in fixes} | {c["term"].lower() for c in cands}
    rows, missing = [], 0
    for rid, res in out.items():
        preds = {p["term"]: p for p in res["predictions"]}
        if rid.startswith("score-"):
            for c in chunks[rid]:
                p = preds.get(c["term"])
                if p is None:
                    missing += 1
                    continue
                rows.append({**{k: c[k] for k in ("term", "segment", "domain", "takes")},
                             **{k: p[k] for k in ("p_fail", "pattern", "likely_heard_as", "reason")},
                             "origin": "pool"})
        else:
            seg = rid.removeprefix("propose-")
            for t, p in preds.items():
                if t.lower() in known:
                    continue
                known.add(t.lower())
                rows.append({"term": t, "segment": seg, "domain": None, "takes": None,
                             **{k: p[k] for k in ("p_fail", "pattern", "likely_heard_as", "reason")},
                             "origin": "proposed"})
    for seg in {r["segment"] for r in rows}:
        ranked = sorted((r for r in rows if r["segment"] == seg), key=lambda r: -r["p_fail"])
        for i, r in enumerate(ranked, 1):
            r["rank"] = i
    rows.sort(key=lambda r: (r["segment"], r["rank"]))
    for r in rows:
        # haiku-r1 listed the correct spelling as a "wrong form" 1,175 times; drop it and repeats.
        r["likely_heard_as"] = list(dict.fromkeys(h for h in r["likely_heard_as"] if h != r["term"]))
        r.update(run=a.run, model=a.model)
    (ROOT / "data/predictions").mkdir(parents=True, exist_ok=True)
    path = ROOT / f"data/predictions/{a.run}.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(json.dumps({"written": str(path), "rows": len(rows), "missing_from_replies": missing,
                      "failed_requests": len(reqs) - len(out)}))


if __name__ == "__main__":
    main()
