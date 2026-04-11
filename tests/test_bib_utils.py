"""Tests for shared BibTeX utilities (bib_utils.py).

Tests the functions extracted from normalize_keys.py and check_duplicates.py
to ensure they maintain identical behavior after the move.
"""

import sys
from pathlib import Path

# Add scripts/ to path so we can import bib_utils directly
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from bib_utils import (
    clean_latex,
    generate_key,
    get_first_author_lastname,
    get_first_title_word,
    normalize_title,
    slugify,
)


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello_world"

    def test_special_characters(self):
        assert slugify("héllo wörld") == "hello_world"

    def test_punctuation_removed(self):
        assert slugify("hello, world!") == "hello_world"

    def test_multiple_spaces(self):
        assert slugify("hello   world") == "hello_world"

    def test_leading_trailing(self):
        assert slugify("  hello  ") == "hello"

    def test_hyphens_to_underscores(self):
        assert slugify("hello-world") == "hello_world"


class TestGetFirstAuthorLastname:
    def test_comma_format(self):
        assert get_first_author_lastname("Smith, John") == "Smith"

    def test_comma_format_multiple_authors(self):
        assert get_first_author_lastname("Smith, John and Doe, Jane") == "Smith"

    def test_natural_format(self):
        assert get_first_author_lastname("John Smith") == "Smith"

    def test_natural_format_middle_name(self):
        assert get_first_author_lastname("John Michael Smith") == "Smith"

    def test_latex_braces(self):
        assert get_first_author_lastname("{Smith}, John") == "Smith"

    def test_empty_returns_unknown(self):
        assert get_first_author_lastname("") == "unknown"


class TestGetFirstTitleWord:
    def test_basic(self):
        assert get_first_title_word("Miniscope imaging in mice") == "miniscope"

    def test_skips_stop_words(self):
        assert get_first_title_word("A new approach to imaging") == "new"
        assert get_first_title_word("The effect of light") == "effect"
        assert get_first_title_word("An overview of methods") == "overview"

    def test_skips_the(self):
        assert get_first_title_word("The UCLA Miniscope") == "ucla"

    def test_strips_latex(self):
        assert get_first_title_word("{Large} field of view") == "large"

    def test_empty_returns_untitled(self):
        assert get_first_title_word("") == "untitled"


class TestGenerateKey:
    def test_basic(self):
        entry = {"author": "Smith, John", "year": "2024", "title": "Miniscope imaging"}
        assert generate_key(entry) == "smith_2024_miniscope"

    def test_skips_stop_words_in_title(self):
        entry = {"author": "Doe, Jane", "year": "2023", "title": "A novel approach"}
        assert generate_key(entry) == "doe_2023_novel"

    def test_missing_author(self):
        entry = {"year": "2024", "title": "Some paper"}
        assert generate_key(entry) == "unknown_2024_some"

    def test_missing_year(self):
        entry = {"author": "Smith, John", "title": "Some paper"}
        assert generate_key(entry) == "smith_0000_some"

    def test_unicode_author(self):
        entry = {"author": "Müller, Hans", "year": "2024", "title": "Brain imaging"}
        assert generate_key(entry) == "muller_2024_brain"

    def test_real_entry_miniscope(self):
        entry = {
            "author": "Guo, Changliang and others",
            "year": "2023",
            "title": "Miniscope-LFOV: A large-field-of-view microscope",
        }
        assert generate_key(entry) == "guo_2023_miniscopelfov"


class TestNormalizeTitle:
    def test_basic(self):
        assert normalize_title("Hello World") == "hello world"

    def test_strips_punctuation(self):
        assert normalize_title("Hello, World!") == "hello world"

    def test_strips_latex(self):
        assert normalize_title("{Hello} World") == "hello world"

    def test_collapses_whitespace(self):
        assert normalize_title("  hello   world  ") == "hello world"

    def test_identical_titles_match(self):
        t1 = normalize_title("A large-field-of-view microscope for mice")
        t2 = normalize_title("A large-field-of-view microscope for mice")
        assert t1 == t2

    def test_case_insensitive(self):
        assert normalize_title("HELLO") == normalize_title("hello")


class TestCleanLatex:
    """Existing function -- verify it still works after we add new functions."""

    def test_removes_braces(self):
        assert clean_latex("{Hello}") == "Hello"

    def test_strips_whitespace(self):
        assert clean_latex("  hello  ") == "hello"

    def test_non_string(self):
        assert clean_latex(42) == "42"
