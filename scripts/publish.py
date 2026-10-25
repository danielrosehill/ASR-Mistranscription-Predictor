#!/usr/bin/env python3
"""Publish the predictor's data to the public HF dataset Hebrish/ASR-Error-Prediction.

Splits every data file by `segment` and uploads one config per file, one split per segment:
  fixes                  data/fixes.jsonl              -> fixes/<segment>.jsonl
  candidates             data/candidates.jsonl         -> candidates/<segment>.jsonl
  predictions-<run>      data/predictions/<run>.jsonl  -> predictions/<run>/<segment>.jsonl
The card is dataset_card.md with the generated `configs:` YAML and a counts table prepended.
Public fields only: words, wrong forms, kinds, counts, dates (never dictation text or row ids).

Usage: with-secrets uv run --with huggingface_hub python scripts/publish.py [--repo R] [--dry-run]
"""
import argparse, json, os, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEGMENTS = ("codeswitching", "tech", "names", "general_english")


def rows(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default="Hebrish/ASR-Error-Prediction")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    sources = [("fixes", ROOT / "data/fixes.jsonl", "fixes"),
               ("candidates", ROOT / "data/candidates.jsonl", "candidates")]
    sources += [(f"predictions-{p.stem}", p, f"predictions/{p.stem}")
                for p in sorted((ROOT / "data/predictions").glob("*.jsonl"))]
    out = Path(tempfile.mkdtemp())
    yaml, table = ["configs:"], ["| Config | " + " | ".join(SEGMENTS) + " |",
                                 "|---|" + "---|" * len(SEGMENTS)]
    for config, path, folder in sources:
        data = rows(path)
        yaml.append(f"- config_name: {config}\n  data_files:")
        counts = []
        for seg in SEGMENTS:
            part = [r for r in data if r["segment"] == seg]
            counts.append(str(len(part)))
            if not part:
                continue
            f = out / folder / f"{seg}.jsonl"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in part))
            yaml.append(f"  - split: {seg}\n    path: {folder}/{seg}.jsonl")
        table.append(f"| `{config}` | " + " | ".join(counts) + " |")
    card = (ROOT / "dataset_card.md").read_text()
    head, body = card.split("---\n", 2)[1:]
    (out / "README.md").write_text(f"---\n{head}{chr(10).join(yaml)}\n---\n"
                                   + body.replace("<!-- counts -->", "\n".join(table)))
    print(json.dumps({"staged": str(out), "files": sorted(str(p.relative_to(out))
                      for p in out.rglob("*") if p.is_file())}, indent=1))
    if a.dry_run:
        return
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(a.repo, repo_type="dataset", private=False, exist_ok=True)
    c = api.upload_folder(repo_id=a.repo, repo_type="dataset", folder_path=str(out),
                          commit_message="Update fixes, candidates and predictions by segment")
    print(c.commit_url)


if __name__ == "__main__":
    main()
