# Central model initialization helper.
# Import model modules and call model_rebuild() to resolve forward refs
from . import athlete, result

# Rebuild models so Pydantic resolves forward refs between modules
try:
    athlete.AthleteDetail.model_rebuild()
except Exception:
    pass

try:
    result.ResultBase.model_rebuild()
    result.ResultInDB.model_rebuild()
except Exception:
    pass
