from app.core.database import Base
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.conversations import models as conversations_models  # noqa: F401
from app.modules.dictation import models as dictation_models  # noqa: F401
from app.modules.evaluations import models as evaluations_models  # noqa: F401
from app.modules.imports import models as imports_models  # noqa: F401
from app.modules.audio import models as audio_models  # noqa: F401
from app.modules.learning import models as learning_models  # noqa: F401
from app.modules.statistics import models as statistics_models  # noqa: F401
from app.modules.tests import models as tests_models  # noqa: F401
from app.modules.texts import models as texts_models  # noqa: F401
from app.modules.users import models as users_models  # noqa: F401
from app.shared import models as shared_models  # noqa: F401

__all__ = ["Base"]
