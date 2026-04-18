from .nickname_changer import NicknameChanger
from .utils import logger

__version__ = '2.0.0'
__author__ = 'Under_Pressure'
__copyright__ = 'Copyright 2026, Under_Pressure'
__mod_name__ = 'Nickname_Changer'

nickname_changer = None


def initialized():
    global nickname_changer
    try:
        nickname_changer = NicknameChanger()
        nickname_changer.init()
        logger.debug('[NicknameChanger] Initialized v%s', __version__)
    except Exception:
        logger.exception('[NicknameChanger] Failed to initialize')


def finalized():
    global nickname_changer
    try:
        if nickname_changer is not None:
            nickname_changer.fini()
        nickname_changer = None
        logger.debug('[NicknameChanger] Finalized v%s', __version__)
    except Exception:
        logger.exception('[NicknameChanger] Failed to finalize')
