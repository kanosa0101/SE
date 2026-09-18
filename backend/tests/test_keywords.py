from app.services.keywords import extract_keywords, normalize_keyword


def test_normalize_keyword_merges_case_and_aliases():
    assert normalize_keyword(" Vision-Language Models ") == "vision-language model"
    assert normalize_keyword("VLM") == "vision-language model"


def test_extract_keywords_ignores_common_words_and_returns_deterministic_terms():
    result = extract_keywords(
        title="Diffusion models for image generation",
        abstract="The diffusion model learns image representations for controlled generation.",
        provided_keywords=[],
        limit=5,
    )

    assert "the" not in result
    assert result
    assert result == extract_keywords(
        title="Diffusion models for image generation",
        abstract="The diffusion model learns image representations for controlled generation.",
        provided_keywords=[],
        limit=5,
    )
