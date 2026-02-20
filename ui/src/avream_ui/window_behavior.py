from __future__ import annotations

from avream_ui.window_behavior_core import WindowCoreMixin
from avream_ui.window_behavior_passwordless import WindowPasswordlessMixin
from avream_ui.window_behavior_phone import WindowPhoneMixin
from avream_ui.window_behavior_service import WindowServiceMixin
from avream_ui.window_behavior_settings import WindowSettingsMixin
from avream_ui.window_behavior_update import WindowUpdateMixin


class WindowBehaviorMixin(
    WindowSettingsMixin,
    WindowCoreMixin,
    WindowServiceMixin,
    WindowPhoneMixin,
    WindowUpdateMixin,
    WindowPasswordlessMixin,
):
    """Aggregates AVream window behavior mixins."""

    pass
