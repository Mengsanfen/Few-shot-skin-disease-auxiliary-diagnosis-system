"""Template context helpers."""

from django.conf import settings


def external_ai_config(request):
    """Expose optional frontend AI widget configuration."""

    return {
        "COZE_TOKEN": getattr(settings, "COZE_TOKEN", ""),
        "COZE_BOT_ID": getattr(settings, "COZE_BOT_ID", ""),
    }
