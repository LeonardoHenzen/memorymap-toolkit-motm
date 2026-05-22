# Django Core
from django.conf import settings

# Third Party Django apps
from constance import config

try:
    from .utils import ensure_maptiler_key
except ImportError:
    def ensure_maptiler_key(url, key):
        return url

def site_settings(request):
    return {
        'config': config,
        'config_base_map_style_url': ensure_maptiler_key(
            config.BASE_MAP_STYLE_URL,
            getattr(config, "MAPTILER_KEY", None)
        )
    }
