from collections.abc import Iterable
import re

from sklearn.feature_extraction.text import TfidfVectorizer


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "using", "via", "with",
    # 代词、限定词、助动词与常用连词，不构成研究方向
    "our", "ours", "their", "them", "they", "its", "these", "those", "there",
    "can", "could", "will", "may", "might", "shall", "should", "would",
    "was", "were", "been", "being", "has", "have", "had", "does", "did",
    "also", "however", "more", "most", "such", "than", "then", "thus",
    "when", "which", "while", "who", "whose", "why", "how", "what", "where",
    "both", "each", "other", "some", "only", "very", "but", "not",
    # 论文写作套话，同样不指向具体研究领域
    "paper", "propose", "proposes", "proposed", "present", "presents", "presented",
    "novel", "based", "method", "methods", "approach", "approaches",
    "result", "results", "show", "shows", "shown", "demonstrate", "demonstrated",
    "achieve", "achieves", "achieved", "improve", "improves", "improved",
    "outperform", "outperforms", "outperformed", "performance", "existing",
    "between", "different", "various", "multiple", "several", "new", "high", "low",
    "one", "two", "three", "within", "across", "without", "toward", "towards",
    "during", "over", "under", "further", "respectively", "significantly",
}

ALIASES = {
    "vlm": "vision-language model",
    "vision language model": "vision-language model",
    "vision language models": "vision-language model",
    "diffusion models": "diffusion model",
    "large language models": "large language model",
}

# 研究方向聚合：作业要求"提取 Top 10 热门领域或热门研究方向"，而非出现最多的词。
# 因此统计排名时先把细粒度关键词按词元映射到研究领域，再按领域覆盖论文数排序；
# 未映射到任何领域的关键词（image、model、deep 等泛化载体词）不参与排名。
# 映射只影响排名聚合，关键词本体与共现图谱保持原样。
RESEARCH_AREAS = [
    ("Object Detection", {"detection", "detector", "yolo", "detr"}),
    ("Segmentation", {"segmentation", "semantic", "instance", "panoptic", "matting", "sam"}),
    ("Diffusion & Generative Models", {"diffusion", "generation", "generative", "denoising", "gan", "vae"}),
    ("Vision-Language & Multimodal", {"vlm", "vision-language", "multimodal", "multi-modal", "llm", "clip", "captioning", "vqa", "text-to-image", "language"}),
    ("3D Perception", {"3d", "point", "depth", "nerf", "reconstruction", "mesh", "slam", "rgb-d", "gaussian"}),
    ("Video Understanding", {"video", "temporal", "action", "tracking", "motion", "frame"}),
    ("Transformers & Attention", {"transformer", "transformers", "attention", "vit", "mamba"}),
    ("Self-Supervised & Representation Learning", {"self-supervised", "contrastive", "representation", "pre-training", "pretraining", "unsupervised", "masked", "embedding"}),
    ("Pose & Keypoint Estimation", {"pose", "keypoint", "skeleton"}),
    ("Adversarial Robustness & Security", {"adversarial", "attack", "robustness", "backdoor"}),
    ("Face & Human Understanding", {"face", "human", "person", "body", "gesture", "gaze"}),
    ("Domain Adaptation & Generalization", {"domain", "adaptation", "generalization", "cross-domain"}),
    ("Autonomous Driving", {"driving", "autonomous", "vehicle", "navigation", "lidar"}),
    ("Medical Imaging", {"medical", "ct", "mri", "x-ray", "lesion", "clinical", "pathology"}),
    ("CNN & Convolutional Networks", {"cnn", "convolutional"}),
]


def research_area_for(name: str) -> str | None:
    """把归一化关键词映射到研究领域；未映射的泛化词返回 None。"""
    tokens = set(name.replace("-", " ").split())
    if not tokens:
        return None
    for area, signals in RESEARCH_AREAS:
        if tokens & signals:
            return area
    return None


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


def canonical_research_area(value: str) -> str | None:
    """Return the display label for a research-area query, if it is one."""
    normalized = normalize_keyword(value)
    for area, _signals in RESEARCH_AREAS:
        if normalize_keyword(area) == normalized:
            return area
    return None


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
