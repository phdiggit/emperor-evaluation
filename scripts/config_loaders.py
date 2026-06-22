from __future__ import annotations

import sys

from shared import config_loaders as _config_loaders


sys.modules[__name__] = _config_loaders
