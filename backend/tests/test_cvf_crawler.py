from pathlib import Path

from app.crawlers.cvf import parse_detail, parse_index


FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_index_deduplicates_and_resolves_relative_links() -> None:
    urls = parse_index(read_fixture("cvf_index.html"), "https://openaccess.thecvf.com")

    assert urls == [
        "https://openaccess.thecvf.com/content/CVPR2024/html/A_Test_Paper_CVPR_2024_paper.html",
        "https://openaccess.thecvf.com/content/CVPR2024/html/Another_Test_Paper_CVPR_2024_paper.html",
    ]


def test_parse_detail_extracts_cvf_metadata() -> None:
    detail_url = "https://openaccess.thecvf.com/content/CVPR2024/html/A_Test_Paper_CVPR_2024_paper.html"

    record = parse_detail(read_fixture("cvf_detail.html"), "CVPR", 2024, detail_url)

    assert record.title == "A Test Paper"
    assert record.conference == "CVPR"
    assert record.year == 2024
    assert record.abstract == "A concise abstract."
    assert record.source_url == detail_url
    assert record.pdf_url is not None
    assert record.pdf_url.endswith(".pdf")


def test_parse_detail_warns_when_abstract_is_missing() -> None:
    detail_url = "https://openaccess.thecvf.com/content/CVPR2024/html/A_Test_Paper_CVPR_2024_paper.html"
    html = read_fixture("cvf_detail.html").replace(
        '<div id="abstract"> A concise abstract. </div>', ""
    )

    record = parse_detail(html, "CVPR", 2024, detail_url)

    assert record.abstract is None
    assert record.parse_warnings == ["missing_abstract"]
