class ServiceError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def openai_service_error(exc):
    """Translate provider errors without exposing keys or raw provider messages."""
    code = getattr(exc, "code", None)
    category = getattr(exc, "type", None)
    status = getattr(exc, "status_code", None)
    if code == "credit_balance_exhausted":
        return ServiceError("OpenAI API credits are exhausted. Add credits in the API billing settings for the account associated with this key, then retry.", 503)
    if code == "insufficient_quota" or category == "insufficient_quota":
        return ServiceError("OpenAI API quota is unavailable. Check API billing and usage limits for the account associated with this key, then retry.", 503)
    if status == 429:
        return ServiceError("OpenAI is temporarily rate limiting requests. Wait briefly, then retry.", 429)
    if status == 401:
        return ServiceError("OpenAI rejected the API key. Update OPENAI_API_KEY in backend/.env and restart the backend.", 503)
    if status in (403, 404):
        return ServiceError("OpenAI denied access to the configured model or resource. Check this API project's permissions and model settings.", 503)
    return ServiceError("Could not complete the OpenAI request. Check the connection and retry.")
