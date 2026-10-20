"""
A minimal, fully deterministic financial-document QA/extraction engine.

This is NOT TrustTrace's core -- it is Module D's "example target
application": a toy system TrustTrace can test end to end without any
external API, so the generic engine's correctness can be proven without
depending on a real LLM. All matching here is literal
term-overlap/regex, clearly labelled as a simulation, not a claim about
real LLM/RAG performance.
"""
from __future__ import annotations
import re
from dataclasses import dataclass


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


@dataclass
class Passage:
    document_id: str
    page_number: int
    passage_id: str
    text: str


def _iter_passages(documents: list[dict]) -> list[Passage]:
    passages: list[Passage] = []
    for doc in documents:
        doc_id = doc["document_id"]
        for page in doc.get("pages", []):
            passages.append(
                Passage(
                    document_id=doc_id,
                    page_number=page["page_number"],
                    passage_id=f"{doc_id}:p{page['page_number']}",
                    text=page.get("text", ""),
                )
            )
    return passages


def search_passages(documents: list[dict], query: str, top_k: int = 5) -> list[dict]:
    """
    Deterministic lexical retrieval: score = overlap between query terms
    and passage terms, normalized by query length. Ties broken by
    document_id/page order for reproducibility.
    """
    query_terms = _tokenize(query)
    scored = []
    for passage in _iter_passages(documents):
        passage_terms = _tokenize(passage.text)
        overlap = len(query_terms & passage_terms)
        score = overlap / len(query_terms) if query_terms else 0.0
        scored.append((score, passage))

    scored.sort(key=lambda item: (-item[0], item[1].document_id, item[1].page_number))
    results = []
    for score, passage in scored[:top_k]:
        if score <= 0:
            continue
        results.append(
            {
                "document_id": passage.document_id,
                "page": passage.page_number,
                "passage_id": passage.passage_id,
                "text": passage.text,
                "score": round(score, 4),
            }
        )
    return results


ABSTAIN_SCORE_THRESHOLD = 0.2


def answer_question(documents: list[dict], query: str, top_k: int = 5) -> dict:
    """
    Answers using only retrieved passages. Abstains rather than inventing
    an answer when no passage clears the relevance threshold.
    """
    passages = search_passages(documents, query, top_k=top_k)
    if not passages or passages[0]["score"] < ABSTAIN_SCORE_THRESHOLD:
        return {
            "answer": None,
            "citations": [],
            "abstained": True,
            "reason": "no passage met the relevance threshold",
            "retrieved_passages": passages,
        }

    best = passages[0]
    return {
        "answer": best["text"],
        "citations": [{"document_id": best["document_id"], "page": best["page"]}],
        "abstained": False,
        "reason": None,
        "retrieved_passages": passages,
    }


def extract_field(documents: list[dict], field_name: str, pattern: str) -> dict:
    """
    Extracts one field via a caller-supplied regex, scanning every page of
    every document. Reports: a single matched value with its citation, a
    conflict when documents disagree, or "missing" when no page matches --
    it never guesses a value that isn't literally present in the text.
    """
    compiled = re.compile(pattern, re.IGNORECASE)
    matches: list[dict] = []
    for passage in _iter_passages(documents):
        found = compiled.search(passage.text)
        if found:
            value = found.group(1) if found.groups() else found.group(0)
            matches.append(
                {
                    "value": value.strip(),
                    "document_id": passage.document_id,
                    "page": passage.page_number,
                }
            )

    distinct_values = {m["value"] for m in matches}

    if not matches:
        return {
            "field_name": field_name,
            "value": None,
            "status": "missing",
            "citations": [],
        }

    if len(distinct_values) > 1:
        return {
            "field_name": field_name,
            "value": None,
            "status": "conflict",
            "conflicting_values": matches,
            "citations": [{"document_id": m["document_id"], "page": m["page"]} for m in matches],
        }

    return {
        "field_name": field_name,
        "value": matches[0]["value"],
        "status": "ok",
        "citations": [{"document_id": m["document_id"], "page": m["page"]} for m in matches],
    }


def extract_fields(documents: list[dict], field_specs: list[dict]) -> dict:
    results = {}
    for spec in field_specs:
        results[spec["field_name"]] = extract_field(documents, spec["field_name"], spec["pattern"])
    return results
