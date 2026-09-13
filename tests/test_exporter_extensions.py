"""Red-phase contract tests for configurable, browser-assisted sources."""

import argparse
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup

import substack_scraper as ss


def _source(**discovery):
    """Build the source shape used by the extension contract."""
    return {
        "name": "Example Journal",
        "base_url": "https://journal.example/",
        "discovery": discovery,
    }


def test_cli_accepts_persistent_browser_launch_without_scraping(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "substack_scraper.py",
            "--url",
            "https://journal.example/",
            "--premium",
            "--persistent-profile",
            "--skip-login",
            "--launch-browser",
        ],
    )

    args = ss.parse_args()

    assert args.launch_browser is True


def test_launch_browser_opens_identity_browser_but_never_enters_scrape_loop(monkeypatch):
    calls = []

    class FakePremiumScraper:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))
            self.driver = Mock()

        def scrape_posts(self, *args, **kwargs):
            calls.append(("scrape", args, kwargs))

    monkeypatch.setattr(ss, "PremiumSubstackScraper", FakePremiumScraper)
    monkeypatch.setattr(
        ss,
        "parse_args",
        lambda: argparse.Namespace(
            url="https://journal.example/",
            directory=None,
            html_directory=None,
            number=0,
            images=False,
            videos=False,
            frontmatter="legacy",
            premium=True,
            browser="chrome",
            headless=False,
            persistent_profile=True,
            skip_login=True,
            launch_browser=True,
            chrome_driver_path="",
            edge_driver_path="",
            chrome_path="",
            edge_path="",
            user_agent="",
            min_delay_seconds=6,
            max_delay_seconds=None,
            max_reuse=None,
            source=None,
        ),
    )

    ss.main()

    assert calls and calls[0][0] == "init"
    assert not [call for call in calls if call[0] == "scrape"]


@pytest.mark.parametrize("mode", ["sitemap", "feed", "html"])
def test_source_definition_requires_base_url_and_supported_discovery_mode(mode):
    source_type = getattr(ss, "SourceDefinition", None)
    assert source_type is not None, "source adapter configuration is not implemented"

    source = source_type.from_dict(_source(mode=mode))

    assert source.base_url == "https://journal.example/"
    assert source.discovery.mode == mode


def test_html_source_definition_requires_index_selector_and_url_filter():
    source_type = getattr(ss, "SourceDefinition", None)
    assert source_type is not None, "source adapter configuration is not implemented"

    source = source_type.from_dict(
        _source(
            mode="html",
            index_url="https://journal.example/archive",
            selector="main a.article-link",
            url_pattern=r"^https://journal\.example/articles/",
        )
    )

    assert source.discovery.index_url.endswith("/archive")
    assert source.discovery.selector == "main a.article-link"
    assert source.discovery.url_pattern.search("https://journal.example/articles/one")


@pytest.mark.parametrize(
    ("mode", "payload", "expected"),
    [
        (
            "sitemap",
            b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://journal.example/articles/one</loc></url></urlset>',
            ["https://journal.example/articles/one"],
        ),
        (
            "feed",
            b"<rss><channel><item><link>https://journal.example/articles/two</link></item></channel></rss>",
            ["https://journal.example/articles/two"],
        ),
    ],
)
def test_configured_xml_discovery_uses_source_base_url(mode, payload, expected, tmp_path):
    source_type = getattr(ss, "SourceDefinition", None)
    assert source_type is not None, "source adapter configuration is not implemented"
    source = source_type.from_dict(_source(mode=mode))

    with patch("substack_scraper.requests.get") as get:
        get.return_value.ok = True
        get.return_value.content = payload
        scraper = ss.SubstackScraper(
            source.base_url,
            str(tmp_path / "md"),
            str(tmp_path / "html"),
            source=source,
        )

    assert scraper.post_urls == expected
    assert get.call_args.args[0] == f"https://journal.example/{mode}.xml"


def test_configured_html_discovery_selects_and_filters_article_links(tmp_path):
    source_type = getattr(ss, "SourceDefinition", None)
    assert source_type is not None, "source adapter configuration is not implemented"
    source = source_type.from_dict(
        _source(
            mode="html",
            index_url="https://journal.example/archive",
            selector="a.article-link",
            url_pattern=r"/articles/",
        )
    )
    index = BeautifulSoup(
        '<a class="article-link" href="/articles/one">one</a>'
        '<a class="article-link" href="/about">about</a>'
        '<a href="/articles/not-selected">wrong selector</a>',
        "html.parser",
    )

    scraper = object.__new__(ss.SubstackScraper)
    scraper.source = source
    scraper.base_substack_url = source.base_url
    scraper._wait_for_request = Mock()
    with patch("substack_scraper.requests.get") as get:
        get.return_value.ok = True
        get.return_value.content = str(index).encode()
        urls = scraper.get_all_post_urls()

    assert urls == ["https://journal.example/articles/one"]


def test_static_source_definition_requires_non_empty_urls_list():
    source_type = getattr(ss, "SourceDefinition", None)
    assert source_type is not None, "source adapter configuration is not implemented"

    with pytest.raises(ValueError, match="urls"):
        source_type.from_dict(_source(mode="static"))

    source = source_type.from_dict(
        _source(mode="static", urls=["https://journal.example/courses/one"])
    )
    assert source.discovery.mode == "static"
    assert source.discovery.urls == ("https://journal.example/courses/one",)


def test_static_discovery_returns_configured_urls_without_fetching(tmp_path):
    source_type = getattr(ss, "SourceDefinition", None)
    assert source_type is not None, "source adapter configuration is not implemented"
    source = source_type.from_dict(
        _source(mode="static", urls=["https://journal.example/courses/one"])
    )

    adapter_type = getattr(ss, "GenericSourceScraper", None)
    adapter = adapter_type(source=source, html_save_dir=str(tmp_path / "html"))
    with patch("substack_scraper.requests.get") as get:
        urls = adapter._discover_pages()

    get.assert_not_called()
    assert urls == ["https://journal.example/courses/one"]


def test_generic_source_uses_browser_driver_when_configured(tmp_path):
    adapter_type = getattr(ss, "GenericSourceScraper", None)
    source_type = getattr(ss, "SourceDefinition", None)
    source = source_type.from_dict(
        _source(mode="static", urls=["https://notion.example/course-one"])
    )

    driver = Mock()
    driver.page_source = "<html><body>rendered content</body></html>"
    driver.execute_script.return_value = 42

    adapter = adapter_type(
        source=source, html_save_dir=str(tmp_path / "html"), driver=driver
    )
    with patch("substack_scraper.requests.get") as get, patch("substack_scraper.sleep"):
        html = adapter._fetch_html("https://notion.example/course-one")

    get.assert_not_called()
    driver.get.assert_called_once_with("https://notion.example/course-one")
    assert html == "<html><body>rendered content</body></html>"


def test_wait_for_render_polls_until_body_text_length_is_stable(tmp_path):
    adapter_type = getattr(ss, "GenericSourceScraper", None)
    source_type = getattr(ss, "SourceDefinition", None)
    source = source_type.from_dict(
        _source(mode="static", urls=["https://notion.example/course-one"])
    )

    driver = Mock()
    driver.execute_script.side_effect = [10, 25, 25, 25]

    adapter = adapter_type(
        source=source, html_save_dir=str(tmp_path / "html"), driver=driver
    )
    with patch("substack_scraper.sleep") as wait:
        adapter._wait_for_render(poll=0.1)

    assert wait.call_count == 4
    assert driver.execute_script.call_count == 4


def test_min_and_max_delay_are_optional_and_validated(tmp_path):
    scraper = ss.SubstackScraper(
        "https://journal.example/p/post",
        str(tmp_path / "md"),
        str(tmp_path / "html"),
        min_delay_seconds=1.5,
        max_delay_seconds=4.5,
    )

    assert scraper.min_delay_seconds == 1.5
    assert scraper.max_delay_seconds == 4.5

    with pytest.raises(ValueError, match="max_delay_seconds"):
        ss.SubstackScraper(
            "https://journal.example/p/post",
            str(tmp_path / "md2"),
            str(tmp_path / "html2"),
            min_delay_seconds=4,
            max_delay_seconds=3,
        )


def test_request_jitter_is_sampled_between_min_and_max(tmp_path):
    scraper = ss.SubstackScraper(
        "https://journal.example/p/post",
        str(tmp_path / "md"),
        str(tmp_path / "html"),
        min_delay_seconds=2,
        max_delay_seconds=5,
    )
    scraper._last_request_at = 100

    with patch("substack_scraper.monotonic", return_value=100), patch(
        "substack_scraper.random.uniform", return_value=3.25
    ) as uniform, patch("substack_scraper.sleep") as wait:
        scraper._wait_for_request()

    uniform.assert_called_once_with(2, 5)
    wait.assert_called_once_with(3.25)


def test_retry_backoff_remains_exponential_and_separate_from_request_jitter(tmp_path):
    scraper = ss.SubstackScraper(
        "https://journal.example/p/post",
        str(tmp_path / "md"),
        str(tmp_path / "html"),
        min_delay_seconds=0,
        max_delay_seconds=10,
    )
    too_many = Mock(content=b"<html><body><pre>too many requests</pre></body></html>")
    ok = Mock(content=b"<html><body><h1>ready</h1></body></html>")
    with patch("substack_scraper.requests.get", side_effect=[too_many, ok]), patch(
        "substack_scraper.random.uniform", return_value=0
    ) as uniform, patch("substack_scraper.sleep") as wait:
        scraper.get_url_soup("https://journal.example/p/post")

    uniform.assert_called_once_with(-0.4, 0.4)
    wait.assert_called_once_with(2)


def test_premium_scraper_accepts_max_reuse_and_preserves_old_tabs(tmp_path):
    driver = Mock(window_handles=["tab-1"])
    with patch.object(ss.BrowserManager, "create_driver", return_value=driver), patch(
        "substack_scraper.sleep"
    ):
        scraper = ss.PremiumSubstackScraper(
            "https://journal.example/p/post",
            str(tmp_path / "md"),
            str(tmp_path / "html"),
            browser="chrome",
            use_persistent_profile=True,
            skip_login=True,
            max_reuse=3,
        )

    assert scraper.max_reuse == 3
    assert scraper.reuse_count >= 1
    assert scraper.driver.window_handles == ["tab-1"]


def test_tab_rotation_uses_random_count_1_through_max_and_opens_same_window_tab(tmp_path):
    class FakeDriver:
        def __init__(self):
            self.window_handles = ["tab-1"]
            self.switch_to = Mock()
            self.execute_script_calls = []

        def execute_script(self, script, url):
            self.execute_script_calls.append((script, url))
            self.window_handles.append("tab-2")

    driver = FakeDriver()
    scraper = object.__new__(ss.PremiumSubstackScraper)
    scraper.driver = driver
    scraper.max_reuse = 3
    scraper.reuse_count = 3

    with patch("substack_scraper.random.randint", return_value=2) as randint:
        scraper._open_next_scrape_tab("https://journal.example/articles/two")

    randint.assert_called_with(1, 3)
    assert driver.execute_script_calls == [
        ("window.open(arguments[0], '_blank');", "https://journal.example/articles/two")
    ]
    driver.switch_to.window.assert_called_once_with("tab-2")
    assert driver.window_handles == ["tab-1", "tab-2"]


def test_non_substack_source_keeps_html_and_reports_missing_formatted_markdown_support(capsys):
    adapter_type = getattr(ss, "GenericSourceScraper", None)
    assert adapter_type is not None, "generic source adapter is not implemented"

    adapter = adapter_type(source=_source(mode="html"))
    adapter.scrape(["https://journal.example/articles/one"])

    assert "formatted Markdown" in capsys.readouterr().out


def test_substack_specific_extraction_handlers_remain_available():
    assert hasattr(ss.BaseSubstackScraper, "_extract_note_data")
    assert hasattr(ss.BaseSubstackScraper, "extract_post_data")
    assert hasattr(ss, "detect_videos_from_soup")
    assert hasattr(ss, "get_video_stream_url")


def test_cli_loads_json_source_definition_and_uses_generic_adapter(monkeypatch, tmp_path):
    config_path = tmp_path / "source.json"
    config_path.write_text(
        json.dumps(
            _source(
                mode="html",
                index_url="https://journal.example/archive",
                selector="a.article-link",
                url_pattern=r"/articles/",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "substack_scraper.py",
            "--source-config",
            str(config_path),
            "--number",
            "1",
        ],
    )

    captured = {}

    class FakeGenericSourceScraper:
        def __init__(self, source, **kwargs):
            captured["source"] = source
            captured["kwargs"] = kwargs

        def scrape_posts(self, number):
            captured["number"] = number

    monkeypatch.setattr(ss, "GenericSourceScraper", FakeGenericSourceScraper)

    ss.main()

    assert captured["source"].base_url == "https://journal.example/"
    assert captured["source"].discovery.selector == "a.article-link"
    assert captured["number"] == 1


def test_cli_generic_source_saves_raw_html_and_reports_unsupported_markdown(
    monkeypatch, tmp_path, capsys
):
    config_path = tmp_path / "source.json"
    config_path.write_text(
        json.dumps(
            _source(
                mode="html",
                index_url="https://journal.example/archive",
                selector="a.article-link",
                url_pattern=r"/articles/",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "substack_scraper.py",
            "--source-config",
            str(config_path),
            "--html-directory",
            str(tmp_path / "html"),
            "--number",
            "1",
        ],
    )

    index_response = Mock(
        ok=True,
        content=b'<a class="article-link" href="/articles/one">one</a>',
    )
    page_response = Mock(
        ok=True,
        content=b"<html><body><h1>One</h1><p>Raw source page</p></body></html>",
    )
    with patch("substack_scraper.requests.get", side_effect=[index_response, page_response]):
        ss.main()

    saved_pages = list((tmp_path / "html").rglob("*.html"))
    assert saved_pages
    assert "Raw source page" in saved_pages[0].read_text(encoding="utf-8")
    assert "formatted Markdown" in capsys.readouterr().out


def test_cli_browser_render_uses_driver_and_quits_when_done(monkeypatch, tmp_path):
    config_path = tmp_path / "source.json"
    config_path.write_text(
        json.dumps(_source(mode="static", urls=["https://notion.example/course-one"])),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "substack_scraper.py",
            "--source-config",
            str(config_path),
            "--html-directory",
            str(tmp_path / "html"),
            "--browser-render",
            "--headless",
        ],
    )

    driver = Mock()
    driver.page_source = "<html><body>rendered</body></html>"
    driver.execute_script.return_value = 7

    with patch.object(
        ss.BrowserManager, "create_driver", return_value=driver
    ) as create_driver, patch("substack_scraper.sleep"):
        ss.main()

    create_driver.assert_called_once()
    assert create_driver.call_args.kwargs["headless"] is True
    driver.get.assert_called_once_with("https://notion.example/course-one")
    driver.quit.assert_called_once()

    saved_pages = list((tmp_path / "html").rglob("*.html"))
    assert saved_pages
    assert "rendered" in saved_pages[0].read_text(encoding="utf-8")
