import app.services.keywords as keywords_module
from app.services.keywords import extract_keywords, normalize_keyword, research_area_for


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


def test_research_area_for_maps_direction_words_and_skips_generic_terms():
    assert research_area_for("detection") == "Object Detection"
    assert research_area_for("object detection") == "Object Detection"
    assert research_area_for("diffusion model") == "Diffusion & Generative Models"
    assert research_area_for("llm") == "Vision-Language & Multimodal"
    assert research_area_for("vision transformer") == "Transformers & Attention"
    assert research_area_for("point cloud") == "3D Perception"
    # 泛化载体词不映射到任何领域，自然退出热门方向排名
    for generic in ("model", "image", "data", "learning", "deep", "training", "network", "abo"):
        assert research_area_for(generic) is None


def test_batch_keyword_extraction_returns_one_deterministic_result_per_paper():
    extractor = getattr(keywords_module, "extract_scored_keywords_batch", None)
    assert callable(extractor)

    results = extractor(
        [
            ("Diffusion models for image generation", "Diffusion models generate images.", []),
            ("Vision-language model", "A model aligns vision and language.", ["VLM"]),
        ],
        limit=5,
    )

    assert len(results) == 2
    assert results[1][0][0] == "vision-language model"
    assert results == extractor(
        [
            ("Diffusion models for image generation", "Diffusion models generate images.", []),
            ("Vision-language model", "A model aligns vision and language.", ["VLM"]),
        ],
        limit=5,
    )
