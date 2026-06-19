"""Effective LLM provider resolution.

A deploy should only need an API key to turn AI on — setting ``ANTHROPIC_API_KEY``
(or ``OPENAI_API_KEY``) auto-selects that provider without also setting
``LLM_PROVIDER``. An explicit non-noop ``llm_provider`` always wins.
"""

from __future__ import annotations

from docos.settings import Settings


def test_noop_without_key_stays_offline():
    s = Settings(llm_provider="noop", anthropic_api_key=None, openai_api_key=None)
    assert s.effective_llm_provider == "noop"
    assert s.ai_enabled is False


def test_anthropic_key_auto_enables_provider():
    s = Settings(llm_provider="noop", anthropic_api_key="sk-ant-test")
    assert s.effective_llm_provider == "anthropic"
    assert s.ai_enabled is True


def test_openai_key_auto_enables_provider():
    s = Settings(llm_provider="noop", openai_api_key="sk-openai-test")
    assert s.effective_llm_provider == "openai"
    assert s.ai_enabled is True


def test_anthropic_preferred_when_both_keys_present():
    s = Settings(llm_provider="noop", anthropic_api_key="a", openai_api_key="o")
    assert s.effective_llm_provider == "anthropic"


def test_explicit_provider_wins_over_autodetect():
    s = Settings(llm_provider="openai", anthropic_api_key="a", openai_api_key="o")
    assert s.effective_llm_provider == "openai"
