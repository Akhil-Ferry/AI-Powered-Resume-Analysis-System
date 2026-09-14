import httpx
import pytest
from openai import RateLimitError
from services.errors import openai_service_error


@pytest.mark.parametrize("code,category,status,message", [
    ("credit_balance_exhausted", "insufficient_quota", 503, "credits are exhausted"),
    ("insufficient_quota", "insufficient_quota", 503, "quota is unavailable"),
    ("rate_limit_exceeded", "requests", 429, "temporarily rate limiting"),
])
def test_quota_and_throttling_are_distinguished(code, category, status, message):
    response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/embeddings"))
    error = RateLimitError("private upstream content", response=response, body={"code": code, "type": category})
    translated = openai_service_error(error)
    assert translated.status == status
    assert message in str(translated)
    assert "private upstream content" not in str(translated)
