from app.services.keywords import extract_keywords, is_informative_keyword, normalize_keyword


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


def test_extract_keywords_filters_academic_boilerplate_terms():
    result = extract_keywords(
        title="our proposed method can detect objects in novel scenes",
        abstract="We present our approach and show that the results improve over previous methods.",
        provided_keywords=[],
        limit=8,
    )

    for boilerplate in ("our", "can", "method", "propose", "result", "show"):
        assert boilerplate not in result
    assert "object" in result


def test_is_informative_keyword_filters_generic_and_fragment_terms():
    for generic in ("model", "image", "data", "learning", "dataset", "feature", "object", "task"):
        assert not is_informative_keyword(generic)
    # 论文自起名缩写碎片不进入排名
    for fragment in ("abo", "aat", "xyz"):
        assert not is_informative_keyword(fragment)
    # 常见技术路线缩写与研究方向词保留
    for informative in ("gan", "vit", "nerf", "detection", "segmentation", "diffusion", "3d"):
        assert is_informative_keyword(informative)
