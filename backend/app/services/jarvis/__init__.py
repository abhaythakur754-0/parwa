"""
Jarvis service package — jarvis_service.py split submodules only.

DO NOT add domain re-exports here — they cause circular imports because
the flat jarvis_* service files import from jarvis_service which imports
from this package.

Domain organization is provided by the other domain folders (auth/, billing/, etc.)
which use lazy re-exports.
"""

from app.services.jarvis.chat import *  # noqa: F401,F403
from app.services.jarvis.payment import *  # noqa: F401,F403
from app.services.jarvis.tickets import *  # noqa: F401,F403
from app.services.jarvis.handoff import *  # noqa: F401,F403
from app.services.jarvis.utils import *  # noqa: F401,F403
