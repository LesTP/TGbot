"""Tests for summarization module init and exports."""

import summarization


class TestModuleExports:
    def test_all_public_names_importable(self):
        expected = [
            "generate_deep_dive",
            "generate_quick_hit",
            "LLMConfig",
            "SummaryResult",
            "LLMAPIError",
            "LLMResponseError",
            "InsufficientContentError",
            "LLMProvider",
            "create_provider",
        ]
        for name in expected:
            assert hasattr(summarization, name), f"{name} not importable from summarization"

    def test_all_list_matches_expected(self):
        expected = {
            "generate_deep_dive",
            "generate_quick_hit",
            "LLMConfig",
            "SummaryResult",
            "LLMAPIError",
            "LLMResponseError",
            "InsufficientContentError",
            "LLMProvider",
            "create_provider",
        }
        assert set(summarization.__all__) == expected

    def test_no_unexpected_exports(self):
        assert len(summarization.__all__) == 9
