# -*- coding: utf-8 -*-
import json
import sys

from .utils import logger

try:
    import ResMgr
except ImportError:
    ResMgr = None

try:
    from helpers import getClientLanguage
except ImportError:
    def getClientLanguage():
        return "en"

IS_PYTHON2 = sys.version_info[0] == 2


class TranslationError(Exception):
    pass


class TranslationManager(object):

    def __init__(self):
        self._defaultTranslationsMap = {}
        self._translationsMap = {}
        self._currentLanguage = None
        self._translationCache = {}
        self._translationsLoaded = False
        self.fallbackLanguage = "en"
        self.translationPathTemplate = "mods/under_pressure.NicknameChanger/{}.json"

    def _safeJsonLoad(self, content, language):
        try:
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            return json.loads(content)
        except (ValueError, TypeError, UnicodeDecodeError) as e:
            logger.error("[TranslationManager] Failed to parse JSON for language %s: %s" % (language, e))
            return None

    def _loadLanguageFile(self, language):
        if ResMgr is None:
            return None
        try:
            translationPath = self.translationPathTemplate.format(language)
            translationsRes = ResMgr.openSection(translationPath)

            if translationsRes is None:
                logger.debug("[TranslationManager] Translation file not found for: %s" % language)
                return None

            content = translationsRes.asBinary
            if not content:
                logger.debug("[TranslationManager] Empty translation file for: %s" % language)
                return None

            return self._safeJsonLoad(content, language)

        except Exception as e:
            logger.error("[TranslationManager] Error loading translation file for %s: %s" % (language, e))
            return None

    def _validateTranslations(self, translations, language):
        if not isinstance(translations, dict):
            logger.error("[TranslationManager] Invalid format for %s: expected dict, got %s" % (
                language, type(translations).__name__))
            return False
        return True

    def loadTranslations(self, forceReload=False):
        if self._translationsLoaded and not forceReload:
            return True

        try:
            defaultTranslations = self._loadLanguageFile(self.fallbackLanguage)

            if defaultTranslations is None:
                self._defaultTranslationsMap = self._getHardcodedDefaults()
                self._translationsMap = self._defaultTranslationsMap.copy()
                self._translationsLoaded = True
                return True

            if not self._validateTranslations(defaultTranslations, self.fallbackLanguage):
                return False

            self._defaultTranslationsMap = defaultTranslations

            try:
                clientLanguage = getClientLanguage()
            except Exception:
                clientLanguage = self.fallbackLanguage

            self._currentLanguage = clientLanguage

            if clientLanguage != self.fallbackLanguage:
                clientTranslations = self._loadLanguageFile(clientLanguage)

                if clientTranslations is not None and self._validateTranslations(clientTranslations, clientLanguage):
                    self._translationsMap = clientTranslations
                else:
                    self._translationsMap = defaultTranslations.copy()
            else:
                self._translationsMap = defaultTranslations.copy()

            self._translationCache.clear()
            self._translationsLoaded = True
            return True

        except Exception as e:
            logger.error("[TranslationManager] Critical error during translation loading: %s" % e)
            self._defaultTranslationsMap = self._getHardcodedDefaults()
            self._translationsMap = self._defaultTranslationsMap.copy()
            self._translationsLoaded = True
            return True

    def _getHardcodedDefaults(self):
        return {
            "modname": "Nickname Changer",
            "general.enable.header": "Enable mod",
            "general.enable.body": "Master toggle. When off, all hooks are bypassed and the original name is shown.",
            "general.nickname.header": "Nickname",
            "general.nickname.body": "Replaces your real nickname everywhere in the client. Required.",
            "general.clanTag.header": "Clan tag",
            "general.clanTag.body": "Replaces your clan abbreviation. Leave empty to keep the original.",
            "general.hideAll.header": "Hide all nicknames",
            "general.hideAll.body": "Replace ALL players nicknames with '???' (visible only to you). Your own nickname is still replaced by the value above.",
            "general.hideServer.header": "Hide server number",
            "general.hideServer.body": "Hides your server/cluster number in the hangar header and in battle (e.g. '#1234' suffix is removed from your name).",
        }

    def getCurrentLanguage(self):
        return self._currentLanguage or self.fallbackLanguage

    def initialize(self):
        try:
            self.loadTranslations()
        except Exception as e:
            logger.error("[TranslationManager] Critical error initializing translations: %s" % e)


g_translationManager = TranslationManager()
g_translationManager.initialize()


class TranslationBase(object):

    def __init__(self, tokenName, manager=None):
        self._tokenName = tokenName
        self._cachedValue = None
        self._manager = manager or g_translationManager

    def __get__(self, instance, owner=None):
        if self._cachedValue is None:
            self._cachedValue = self._generateTranslation()
        return self._cachedValue

    def _generateTranslation(self):
        raise NotImplementedError

    def invalidateCache(self):
        self._cachedValue = None


class TranslationElement(TranslationBase):

    def _generateTranslation(self):
        if not self._manager._translationsLoaded:
            self._manager.loadTranslations()

        cached = self._manager._translationCache.get(self._tokenName)
        if cached is not None:
            return cached

        translation = None
        if self._tokenName in self._manager._translationsMap:
            translation = self._manager._translationsMap[self._tokenName]
        elif self._tokenName in self._manager._defaultTranslationsMap:
            translation = self._manager._defaultTranslationsMap[self._tokenName]
        else:
            translation = self._tokenName.replace('.', ' ').replace('_', ' ').title()

        self._manager._translationCache[self._tokenName] = translation
        return translation


class Translator(object):
    MOD_NAME = TranslationElement("modname")
    ENABLE_HEADER = TranslationElement("general.enable.header")
    ENABLE_BODY = TranslationElement("general.enable.body")
    NICKNAME_HEADER = TranslationElement("general.nickname.header")
    NICKNAME_BODY = TranslationElement("general.nickname.body")
    CLAN_TAG_HEADER = TranslationElement("general.clanTag.header")
    CLAN_TAG_BODY = TranslationElement("general.clanTag.body")
    HIDE_ALL_HEADER = TranslationElement("general.hideAll.header")
    HIDE_ALL_BODY = TranslationElement("general.hideAll.body")
    HIDE_SERVER_HEADER = TranslationElement("general.hideServer.header")
    HIDE_SERVER_BODY = TranslationElement("general.hideServer.body")


def getTranslation(key):
    if not g_translationManager._translationsLoaded:
        g_translationManager.loadTranslations()

    if key in g_translationManager._translationsMap:
        return g_translationManager._translationsMap[key]
    elif key in g_translationManager._defaultTranslationsMap:
        return g_translationManager._defaultTranslationsMap[key]
    return key.replace('.', ' ').replace('_', ' ').title()


def createTooltip(header=None, body=None, note=None, attention=None):
    result = ''
    if header is not None:
        result += '{HEADER}%s{/HEADER}' % header
    if body is not None:
        result += '{BODY}%s{/BODY}' % body
    if note is not None:
        result += '{NOTE}%s{/NOTE}' % note
    if attention is not None:
        result += '{ATTENTION}%s{/ATTENTION}' % attention
    return result
