"""
Módulo de componentes reutilizáveis da UI.

Componentes são elementos visuais independentes
que podem ser combinados para construir páginas.
"""

from .base import BaseComponent
from .buttons import (
    ButtonComponent,
    ActionButton,
    NavigationButton,
    CancelButton,
    ConfirmationDialog,
)
from .forms import (
    LoginForm,
    SearchInput,
    NumberInput,
    SelectBox,
    TextArea,
    Checkbox,
)
from .metrics import (
    MetricCard,
    MetricsRow,
    ProgressMetrics,
)
from .progress import (
    ProgressBar,
    ProcessingStatus,
    TimeEstimate,
)
from .lists import (
    ItemList,
    ProfileList,
    TaskList,
    TagList,
    ProcessList,
)

__all__ = [
    # Base
    "BaseComponent",
    
    # Buttons
    "ButtonComponent",
    "ActionButton",
    "NavigationButton",
    "CancelButton",
    "ConfirmationDialog",
    
    # Forms
    "LoginForm",
    "SearchInput",
    "NumberInput",
    "SelectBox",
    "TextArea",
    "Checkbox",
    
    # Metrics
    "MetricCard",
    "MetricsRow",
    "ProgressMetrics",
    
    # Progress
    "ProgressBar",
    "ProcessingStatus",
    "TimeEstimate",
    
    # Lists
    "ItemList",
    "ProfileList",
    "TaskList",
    "TagList",
    "ProcessList",
]