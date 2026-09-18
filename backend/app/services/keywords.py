from collections.abc import Iterable
import re

from sklearn.feature_extraction.text import TfidfVectorizer


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "using", "via", "with",
}

ALIASES = {
    "vlm": "vision-language model",
    "vision language model": "vision-language model",
    "vision language models": "vision-language model",
    "diffusion models": "diffusion model",
    "large language models": "large language model",
}


def _singularize(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def normalize_keyword(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip().lower().replace("_", " "))
    if not value:
        return ""
    if value in ALIASES:
        return ALIASES[value]
    value = re.sub(r"[^a-z0-9\- ]", " ", value)
    tokens = [_singularize(token) for token in value.split() if token not in STOP_WORDS]
    normalized = " ".join(tokens)
    return ALIASES.get(normalized, normalized)


def extract_scored_keywords(
    title: str | None,
    abstract: str | None,
    provided_keywords: Iterable[str] | None,
    limit: int = 10,
) -> list[tuple[str, float, str]]:
    provided = [normalize_keyword(item) for item in (provided_keywords or [])]
    provided = list(dict.fromkeys(item for item in provided if item))
    if provided:
        return [(item, 1.0, "provided") for item in provided[:limit]]

    text = " ".join(part for part in (title or "", abstract or "") if part).strip()
    if not text:
        return []
    vectorizer = TfidfVectorizer(
        stop_words=list(STOP_WORDS),
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9\-]{2,}\b",
    )
    try:
        matrix = vectorizer.fit_transform([text])
    except ValueError:
        return []
    terms = vectorizer.get_feature_names_out()
    scores = matrix.toarray()[0]
    ranked = sorted(zip(terms, scores), key=lambda item: (-float(item[1]), item[0]))
    result: list[tuple[str, float, str]] = []
    seen: set[str] = set()
    for term, score in ranked:
        normalized = normalize_keyword(term)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append((normalized, round(float(score), 6), "tfidf"))
        if len(result) == limit:
            break
    return result


def extract_keywords(
    title: str | None,
    abstract: str | None,
    provided_keywords: Iterable[str] | None,
    limit: int = 10,
) -> list[str]:
    return [name for name, _, _ in extract_scored_keywords(title, abstract, provided_keywords, limit)]
