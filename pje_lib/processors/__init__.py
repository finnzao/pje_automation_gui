"""
Processadores para diferentes tipos de operações.
"""

from .base_processor import BaseProcessor
from .task_processor import TaskProcessor
from .tag_processor import TagProcessor
from .number_processor import NumberProcessor
from .subject_processor import SubjectProcessor

__all__ = [
    "BaseProcessor",
    "TaskProcessor", 
    "TagProcessor",
    "NumberProcessor",
    "SubjectProcessor"
]