from .base import BasePage
from .login import LoginPage
from .select_profile import SelectProfilePage
from .main_menu import MainMenuPage
from .download_by_task import DownloadByTaskPage
from .download_by_tag import DownloadByTagPage
from .download_by_number import DownloadByNumberPage
from .processing import ProcessingTaskPage, ProcessingTagPage, ProcessingNumberPage
from .result import ResultPage

__all__ = [
    "BasePage",
    "LoginPage",
    "SelectProfilePage",
    "MainMenuPage",
    "DownloadByTaskPage",
    "DownloadByTagPage",
    "DownloadByNumberPage",
    "ProcessingTaskPage",
    "ProcessingTagPage",
    "ProcessingNumberPage",
    "ResultPage",
]