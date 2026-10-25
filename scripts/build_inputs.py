#!/usr/bin/env python3
"""Build the predictor's inputs: the fix list (positives) and the candidate pools, by segment.

Writes data/fixes.jsonl and data/candidates.jsonl (one row per word, each with a `segment`).

Segments (the dataset's splits), assigned in this order from the error list's `kinds`:
  codeswitching    kinds has hebrew or yiddish (romanized Hebrew/Yiddish terms)
  tech             kinds has tech, linux, ai_interactions or smart_home
  names            kinds has name or personal (people, companies, projects)
  general_english  everything else (kind `other`: ordinary English words)

Sources:
  fixes       Hebrish/ASR-Error-List words.jsonl (public HF dataset), pinned with --error-list-rev
  candidates  codeswitching: Hebrish-App data/lexicon.json (the public lexicon, field `t`; `d` is its
              domain, `n` the recorded takes); tech: ASR-Training data/tech-terms.json and
              data/tech-packs/*.json (`term`). Words already on the fix list are left out.
              names and general_english have no pool; predict_llm.py asks for open proposals.

Usage: python3 scripts/build_inputs.py [--repos ~/repos/github/audio-dictation] [--error-list-rev main]
"""
import argparse, glob, json, subprocess, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERROR_LIST = "Hebrish/ASR-Error-List"
ORDER = [("codeswitching", {"hebrew", "yiddish"}),
         ("tech", {"tech", "linux", "ai_interactions", "smart_home"}),
         ("names", {"name", "personal"})]


def segment(kinds):
    for name, ks in ORDER:
        if ks & set(kinds):
            return name
    return "general_english"


def hf_rev(repo, rev):
    with urllib.request.urlopen(f"https://huggingface.co/api/datasets/{repo}/revision/{rev}") as r:
        return json.load(r)["sha"]


def git_rev(path):
    return subprocess.run(["git", "-C", str(path), "rev-parse", "--short=12", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repos", default=str(Path.home() / "repos/github/audio-dictation"))
    ap.add_argument("--error-list-rev", default="main")
    a = ap.parse_args()
    repos = Path(a.repos)
    sha = hf_rev(ERROR_LIST, a.error_list_rev)

    url = f"https://huggingface.co/datasets/{ERROR_LIST}/resolve/{sha}/words.jsonl"
    with urllib.request.urlopen(url) as r:
        words = [json.loads(l) for l in r.read().decode().splitlines() if l.strip()]
    fixes = [{"word": w["word"], "segment": segment(w["kinds"]), "heard_as": w["heard_as"],
              "kinds": w["kinds"], "meaning": w.get("meaning"), "occurrences": w["occurrences"],
              "models": w["models"], "first_seen": w["first_seen"], "last_seen": w.get("last_seen"),
              "label": "orthographic" if all(h.lower() == w["word"].lower().replace("-", "")
                                             or h.lower() == w["word"].lower() for h in w["heard_as"])
                       else "acoustic",
              "source": "dictation", "error_list_rev": sha[:12]} for w in words]
    known = {f["word"].lower() for f in fixes}

    cands, seen = [], set()
    lex_path = repos / "Hebrish-App/data/lexicon.json"
    lex = json.loads(lex_path.read_text())
    for t in lex["terms"]:
        k = t["t"].lower()
        if k in known or k in seen:
            continue
        seen.add(k)
        cands.append({"term": t["t"], "segment": "codeswitching", "domain": t["d"],
                      "meaning": t.get("m"), "takes": t.get("n"),
                      "pool": f"Hebrish-App/data/lexicon.json@{git_rev(lex_path.parent)}"})
    asr = repos / "ASR-Training"
    for f in [asr / "data/tech-terms.json", *sorted(glob.glob(str(asr / "data/tech-packs/*.json")))]:
        d = json.loads(Path(f).read_text())
        for t in d["terms"] if isinstance(d, dict) else d:
            k = t["term"].lower()
            if k in known or k in seen:
                continue
            seen.add(k)
            cands.append({"term": t["term"], "segment": "tech", "domain": t.get("category"),
                          "meaning": t.get("meaning") or t.get("why"), "takes": None,
                          "pool": f"ASR-Training/{Path(f).relative_to(asr)}@{git_rev(asr)}"})

    (ROOT / "data").mkdir(exist_ok=True)
    for name, rows in (("fixes", fixes), ("candidates", cands)):
        with (ROOT / f"data/{name}.jsonl").open("w") as fh:
            fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    count = lambda rows: {s: sum(r["segment"] == s for r in rows) for s in
                          ("codeswitching", "tech", "names", "general_english")}
    print(json.dumps({"error_list_rev": sha, "fixes": count(fixes), "candidates": count(cands)}))


if __name__ == "__main__":
    main()
