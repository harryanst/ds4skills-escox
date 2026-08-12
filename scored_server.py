
"""
Custom ESCOX scoring server.

Wraps esco_skill_extractor.SkillExtractor directly (instead of its stock CLI
server) so we can return the *actual* cosine-similarity score and the exact
input clause that produced each match, instead of just a pass/fail URI list.

Endpoint:
  POST /extract-skills-scored
  Body: ["text one", "text two", ...]
  Returns: [
    [{"uri": "...", "score": 0.62, "clause": "Deep Learning"}, ...],
    [...],
  ]
  One list per input text, in the same order, sorted by score descending.

Only a low safety floor (ESCOX_FLOOR) is applied here. The real, tunable
match threshold lives in the calling application (DS4Skills' ESCOX Config
admin tab) so it can be adjusted without redeploying this container.
"""
import os
import re

from flask import Flask, request, jsonify
from waitress import serve
from sentence_transformers import util

from esco_skill_extractor import SkillExtractor

TOP_K = int(os.environ.get("ESCOX_TOP_K", "3"))     # candidates kept per clause
FLOOR = float(os.environ.get("ESCOX_FLOOR", "0.3")) # absolute safety floor


class SkillOnlyExtractor(SkillExtractor):
    """We only ever score skills, never occupations — skip loading/embedding
    the occupations taxonomy entirely to cut memory use on constrained hosts
    (e.g. Render's free tier, ~512MB)."""

    def _load_occupations(self):
        self._occupations = None
        self._occupation_ids = []

    def _create_occupation_embeddings(self):
        self._occupation_embeddings = None


print("Loading SkillExtractor (skills only) with its own defaults...")
extractor = SkillOnlyExtractor()

for attr in ("_model", "_skill_embeddings", "_skill_ids", "device"):
    if not hasattr(extractor, attr):
        raise RuntimeError(
            f"SkillExtractor is missing expected attribute {attr!r} — "
            f"the installed esco-skill-extractor version doesn't match what "
            f"this scorer was written against. Available attributes: "
            f"{[a for a in dir(extractor) if not a.startswith('__')]}"
        )

print("Model and ESCO skill embeddings loaded.")


def split_clauses(text):
    """Clause boundaries: newlines, tabs, periods, commas, semicolons, and the
    standalone words 'and'/'or' (word-boundaried — unlike esco_skill_extractor's
    own internal splitter, this won't tear apart words like "algorithms" or
    "coordinate" just because they contain the substring "or")."""
    return [s.strip() for s in re.split(r"\r|\n|\t|\.|\,|\;|\band\b|\bor\b", text or "") if s.strip()]


def score_text(text):
    clauses = split_clauses(text)
    if not clauses:
        return []

    clause_embeddings = extractor._model.encode(
        clauses,
        device=extractor.device,
        normalize_embeddings=True,
        convert_to_tensor=True,
    )
    # Embeddings are normalized, so the dot product is the cosine similarity.
    sims = util.dot_score(clause_embeddings, extractor._skill_embeddings)

    best = {}  # uri -> (score, clause) — keep the highest-scoring clause per skill
    for i, clause in enumerate(clauses):
        row = sims[i]
        k = min(TOP_K, row.shape[0])
        top_scores, top_idx = row.topk(k)
        for score, idx in zip(top_scores.tolist(), top_idx.tolist()):
            if score < FLOOR:
                continue
            uri = extractor._skill_ids[idx]
            if uri not in best or score > best[uri][0]:
                best[uri] = (score, clause)

    results = [
        {"uri": uri, "score": round(score, 4), "clause": clause}
        for uri, (score, clause) in best.items()
    ]
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


app = Flask(__name__)


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/")
def index():
    return jsonify({"service": "ds4skills-escox-scored", "status": "ok"})


@app.route("/extract-skills-scored", methods=["POST"])
def extract_scored():
    texts = request.json
    if not isinstance(texts, list):
        return jsonify({"error": "expected a JSON array of strings"}), 400
    return jsonify([score_text(t) for t in texts])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    print(f"Starting scored ESCOX server on 0.0.0.0:{port}")
    serve(app, host="0.0.0.0", port=port, channel_timeout=1200)
