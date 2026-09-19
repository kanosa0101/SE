import httpx
import pytest

from app.config import Settings
from app.services.lookup import LookupUnavailableError, lookup_title


def openalex_record(title, source_display_name, year=2023):
    return {
        "title": title,
        "publication_year": year,
        "primary_location": {
            "landing_page_url": "https://doi.org/10.1109/cvpr52729.2023.01548",
            "source": {"display_name": source_display_name},
        },
        "authorships": [{"author": {"display_name": "Researcher One"}}],
        "keywords": [{"display_name": "Transformers"}],
    }


def configured_settings():
    return Settings(lookup_url="https://api.openalex.org/works")


def patch_openalex(monkeypatch, results):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, request=request, json={"results": results})

    monkeypatch.setattr(httpx, "get", fake_get)
    return captured


def test_lookup_maps_cvpr_full_name_to_acronym(monkeypatch):
    patch_openalex(
        monkeypatch,
        [
            openalex_record(
                "A ConvNet for the 2020s",
                "2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)",
                year=2022,
            )
        ],
    )

    paper = lookup_title("A ConvNet for the 2020s", configured_settings())

    assert paper.conference == "CVPR"
    assert paper.year == 2022
    assert paper.source == "online"
    assert paper.authors == "Researcher One"


def test_lookup_maps_iccv_and_eccv_full_names(monkeypatch):
    for title, venue, expected in (
        (
            "Vision Transformer with Deformable Attention",
            "IEEE/CVF International Conference on Computer Vision (ICCV)",
            "ICCV",
        ),
        (
            "Swin Transformer: Hierarchical Vision Transformer",
            "European Conference on Computer Vision (ECCV)",
            "ECCV",
        ),
    ):
        patch_openalex(monkeypatch, [openalex_record(title, venue)])

        paper = lookup_title(title, configured_settings())

        assert paper.conference == expected


def test_lookup_rejects_venues_outside_three_conferences(monkeypatch):
    patch_openalex(
        monkeypatch,
        [openalex_record("A ConvNet for the 2020s", "arXiv (Cornell University)")],
    )

    with pytest.raises(LookupUnavailableError) as exc_info:
        lookup_title("A ConvNet for the 2020s", configured_settings())

    assert "不属于" in str(exc_info.value)


def test_lookup_picks_venue_match_from_mixed_results(monkeypatch):
    patch_openalex(
        monkeypatch,
        [
            openalex_record("A ConvNet for the 2020s", "arXiv (Cornell University)"),
            openalex_record(
                "A ConvNet for the 2020s",
                "2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)",
                year=2022,
            ),
        ],
    )

    paper = lookup_title("ConvNeXt: A ConvNet for the 2020s", configured_settings())

    assert paper.conference == "CVPR"


def test_lookup_rejects_venue_match_with_unrelated_title(monkeypatch):
    patch_openalex(
        monkeypatch,
        [
            openalex_record(
                "Completely Different Paper About Segmentation",
                "2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)",
            )
        ],
    )

    with pytest.raises(LookupUnavailableError) as exc_info:
        lookup_title("A ConvNet for the 2020s", configured_settings())

    assert "不够匹配" in str(exc_info.value)


def test_lookup_without_configured_source():
    with pytest.raises(LookupUnavailableError) as exc_info:
        lookup_title("A ConvNet for the 2020s", Settings(lookup_url=None))

    assert "未配置" in str(exc_info.value)
