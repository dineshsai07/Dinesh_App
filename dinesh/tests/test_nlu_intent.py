"""
Regression tests for typo tolerance and intent routing.

Run with:  python3 -m pytest tests/ -q      (from the dinesh/ directory)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nlu import fuzzy_contains, normalize, resolve_app, resolve_folder  # noqa: E402


class TestNormalize:
    @pytest.mark.parametrize("noisy,expected_word", [
        ("opne safari", "open"),
        ("wat is the time", "what"),
        ("take a screenshto", "screenshot"),
        ("open my downlaods folder", "downloads"),
        ("creat a folder", "create"),
        ("whats the batery", "battery"),
        ("show me cpu usag", "usage"),
        ("opne chorme", "chrome"),
        ("check my documnets", "documents"),
        ("how much storag left", "storage"),
        ("hwo mch spac do i hav lft", "space"),
        ("wat can yuo do", "you"),
        ("tel me a jok abt computrs", "joke"),
    ])
    def test_typos_are_corrected(self, noisy, expected_word):
        assert expected_word in normalize(noisy).lower()

    @pytest.mark.parametrize("text", [
        "go to /Users/me/Desktop/x.txt",
        "run script_v2.py",
        "open https://example.com/a?b=1",
    ])
    def test_paths_and_urls_survive(self, text):
        assert normalize(text) == text

    def test_empty_input(self):
        assert normalize("") == ""
        assert normalize("   ") == ""

    def test_correct_text_is_unchanged(self):
        text = "open the downloads folder"
        assert normalize(text) == text


class TestResolveApp:
    def test_exact_match(self):
        assert resolve_app("safari") == "Safari"

    def test_misspelling(self):
        assert resolve_app("safri") == "Safari"

    def test_nickname_maps_to_full_name(self):
        # Only meaningful if Chrome is installed on this machine.
        result = resolve_app("chrome")
        if result is not None:
            assert "Chrome" in result

    def test_nested_utilities_app_is_found(self):
        assert resolve_app("terminal") == "Terminal"

    def test_unknown_app_returns_none(self):
        assert resolve_app("zzzznotanapp") is None

    def test_does_not_match_wildly_different_name(self):
        # "chorme" must never resolve to "Home".
        assert resolve_app("chorme") != "Home"


class TestResolveFolder:
    @pytest.mark.parametrize("query,expected", [
        ("downloads", "Downloads"),
        ("downlaods", "Downloads"),
        ("my desktop", "Desktop"),
        ("documnets", "Documents"),
    ])
    def test_known_folders(self, query, expected):
        result = resolve_folder(query)
        assert result is not None and result.name == expected

    def test_unknown_folder(self):
        assert resolve_folder("zzzznotafolder") is None


class TestFuzzyContains:
    def test_match_with_typo(self):
        assert fuzzy_contains("hey dinesh are you there", "hey dinesh")

    def test_no_false_positive(self):
        assert not fuzzy_contains("the weather is nice", "hey dinesh")


class TestIntentRouting:
    """Side-effecting tools are stubbed so nothing actually launches."""

    @pytest.fixture(autouse=True)
    def stub_tools(self, monkeypatch):
        import tools.file_tools as files
        import tools.mac_tools as mac
        import tools.shell_tools as shell
        import tools.web_tools as web

        monkeypatch.setattr(mac, "open_app", lambda a: f"open_app:{a}")
        monkeypatch.setattr(mac, "open_path", lambda p: f"open_path:{p}")
        monkeypatch.setattr(mac, "open_url", lambda u: f"open_url:{u}")
        monkeypatch.setattr(mac, "set_volume", lambda v: f"volume:{v}")
        monkeypatch.setattr(mac, "take_screenshot", lambda: "/tmp/shot.png")
        monkeypatch.setattr(files, "create_folder", lambda p: f"mkdir:{p}")
        monkeypatch.setattr(files, "list_files", lambda p: f"ls:{p}")
        monkeypatch.setattr(web, "web_search", lambda q: f"search:{q}")
        monkeypatch.setattr(shell, "get_time_and_date", lambda: "time")
        monkeypatch.setattr(shell, "get_battery", lambda: "battery")
        monkeypatch.setattr(shell, "get_storage", lambda: "storage")
        monkeypatch.setattr(shell, "get_cpu_usage", lambda: "cpu")
        monkeypatch.setattr(shell, "get_resource_summary", lambda: "resources")

    @pytest.mark.parametrize("text,expected", [
        ("opne safari", "open_app:safari"),
        ("opne chorme", "open_app:chrome"),
        ("open github.com", "open_url:github.com"),
        ("wat is the time", "time"),
        ("whats the batery", "battery"),
        ("hows my disk space", "storage"),
        ("cpu and memory usage", "resources"),
        ("set volume to 40", "volume:40"),
        ("search for python tutorials", "search:python tutorials"),
    ])
    def test_typo_commands_route_correctly(self, text, expected):
        from intent import handle_intent
        assert handle_intent(text) == expected

    def test_misspelled_folder_opens_folder_not_app(self):
        from intent import handle_intent
        result = handle_intent("open my downlaods folder")
        assert result.startswith("open_path:") and result.endswith("Downloads")

    def test_screenshot_with_typo(self):
        from intent import handle_intent
        assert "shot.png" in handle_intent("take a screenshto")

    def test_folder_creation_with_typo(self):
        from intent import handle_intent
        assert handle_intent("creat a folder called test on desktop").endswith("Desktop/test")

    @pytest.mark.parametrize("text", [
        "open safari and search for news",
        "scrape example.com and save it",
        "why is my mac slow",
        "tell me a joke",
        "how are you",
        "",
    ])
    def test_complex_requests_defer_to_llm(self, text):
        from intent import handle_intent
        assert handle_intent(text) is None


class TestGiveUpDetection:
    @pytest.mark.parametrize("reply", [
        "I didn't understand that.",
        "Sorry, could you rephrase?",
        "I'm not sure what you mean, sir.",
    ])
    def test_detects_give_up_replies(self, reply):
        from agent import _is_give_up
        assert _is_give_up(reply)

    @pytest.mark.parametrize("reply", [
        "Opened Chrome, sir.",
        "Storage: 73 GB free.",
    ])
    def test_allows_real_answers(self, reply):
        from agent import _is_give_up
        assert not _is_give_up(reply)


class TestSentenceTrimming:
    def test_decimals_are_preserved(self):
        from agent import _trim_sentences
        reply = "You have 71.3 GB free of 460.4 GB total. That is 85% used."
        assert "71.3 GB" in _trim_sentences(reply)
        assert "460.4 GB" in _trim_sentences(reply)

    def test_long_reply_is_truncated(self):
        from agent import _trim_sentences
        reply = "One. Two. Three. Four. Five."
        assert _trim_sentences(reply, limit=3) == "One. Two. Three."

    def test_short_reply_is_untouched(self):
        from agent import _trim_sentences
        assert _trim_sentences("Done, sir.") == "Done, sir."
