import BigWorld
from PlayerEvents import g_playerEvents

from ..settings import settings
from ..utils import logger, override, try_imports
from .. import data_handlers
from . import Component


class BattleResultsComponent(Component):

    def __init__(self, controller):
        super(BattleResultsComponent, self).__init__(controller)
        self._original_cache_get = None
        self._patched_cache = None
        self._original_create = None
        self._reusable_module = None
        self._subscribed_results = False

    def setup_hooks(self):
        identity = self.identity

        try:
            from gui.battle_results import reusable as reusable_module
            if not getattr(reusable_module, '_nc_createReusableInfo_patched', False):
                original_create = reusable_module.createReusableInfo

                def patched_create(results):
                    if settings.enabled and identity.has_original and isinstance(results, dict):
                        data_handlers.patch_raw_results(results, identity)
                    info = original_create(results)
                    if info and settings.enabled and identity.has_original:
                        data_handlers.patch_reusable_info_players(info, identity)
                        data_handlers.patch_reusable_info_deep(info, identity)
                    return info

                reusable_module.createReusableInfo = patched_create
                reusable_module._nc_createReusableInfo_patched = True
                self._original_create = original_create
                self._reusable_module = reusable_module
                logger.debug("createReusableInfo patched")
        except ImportError:
            logger.debug("gui.battle_results.reusable not available")

        try:
            from gui.battle_results.service import BattleResultsService

            @override(BattleResultsService, 'postResult')
            def hooked_post_result(baseMethod, baseObject, result, needToShowUI=True):
                if settings.enabled:
                    data_handlers.patch_raw_results(result, identity)
                return baseMethod(baseObject, result, needToShowUI)

            priv = '_BattleResultsService__onGetBattleResults'
            if hasattr(BattleResultsService, priv):
                @override(BattleResultsService, priv)
                def hooked_on_get(baseMethod, baseObject, requestID, result):
                    if settings.enabled:
                        data_handlers.patch_raw_results(result, identity)
                    return baseMethod(baseObject, requestID, result)
        except ImportError:
            logger.debug("BattleResultsService not available")

        vo_meta = try_imports(
            lambda: __import__('gui.battle_results.components', fromlist=['vo_meta']).vo_meta,
            lambda: __import__('gui.battle_results', fromlist=['vo_meta']).vo_meta,
        )
        if vo_meta and hasattr(vo_meta, 'PersonalDataBlockVO'):
            @override(vo_meta.PersonalDataBlockVO, 'build')
            def hooked_build(baseMethod, baseObject, reusableInfo, personalInfo):
                if settings.enabled and identity.has_original:
                    if reusableInfo:
                        data_handlers.patch_reusable_info_players(reusableInfo, identity)
                    if personalInfo:
                        data_handlers.patch_personal_info_data(personalInfo, identity)
                return baseMethod(baseObject, reusableInfo, personalInfo)

        BattleResults = try_imports(
            lambda: __import__('gui.Scaleform.daapi.view.lobby.battle_results.battle_results', fromlist=['BattleResults']).BattleResults,
            lambda: __import__('gui.Scaleform.daapi.view.lobby.battle_results', fromlist=['BattleResults']).BattleResults,
        )
        if BattleResults and hasattr(BattleResults, '_populateUI'):
            @override(BattleResults, '_populateUI')
            def hooked_populate_ui(baseMethod, baseObject, *args, **kwargs):
                result = baseMethod(baseObject, *args, **kwargs)
                if settings.enabled and identity.has_original and hasattr(baseObject, '_arenaUniqueID'):
                    data_handlers.patch_battle_results_view(baseObject, identity)
                return result

        try:
            g_playerEvents.onBattleResultsReceived += self._on_battle_results_received
            self._subscribed_results = True
        except Exception as e:
            logger.error("Failed to subscribe onBattleResultsReceived: %s" % e)
            self._subscribed_results = False

    def _on_battle_results_received(self, isPlayerVehicle, results):
        if not settings.enabled:
            return
        if not isPlayerVehicle or not self.identity.has_original:
            return
        if not isinstance(results, dict):
            return
        try:
            data_handlers.patch_raw_results(results, self.identity)
        except Exception as e:
            logger.error("on_battle_results_received: %s" % e)

    def on_lobby_ready(self):
        try:
            player = BigWorld.player()
            if not player or not hasattr(player, 'battleResultsCache'):
                return
            cache = player.battleResultsCache
            if cache is self._patched_cache:
                return
            original_get = cache.get
            if getattr(original_get, '_nc_patched', False):
                self._patched_cache = cache
                return
            identity = self.identity

            def patched_get(arenaUniqueID, callback):
                def modified_callback(code, result):
                    if code > 0 and result and settings.enabled and identity.has_original:
                        data_handlers.patch_raw_results(result, identity)
                    callback(code, result)
                return original_get(arenaUniqueID, modified_callback)

            patched_get._nc_patched = True
            self._original_cache_get = original_get
            cache.get = patched_get
            self._patched_cache = cache
            logger.debug("battleResultsCache.get patched")
        except Exception as e:
            logger.debug("battleResultsCache patch failed: %s" % e)

    def on_avatar_become_non_player(self):
        try:
            if self._patched_cache and self._original_cache_get:
                self._patched_cache.get = self._original_cache_get
                logger.debug("battleResultsCache.get restored")
        except Exception as e:
            logger.debug("restore cache failed: %s" % e)
        finally:
            self._patched_cache = None
            self._original_cache_get = None

    def fini(self):
        if self._subscribed_results:
            try:
                g_playerEvents.onBattleResultsReceived -= self._on_battle_results_received
            except Exception:
                pass
            self._subscribed_results = False

        try:
            if self._reusable_module and self._original_create:
                self._reusable_module.createReusableInfo = self._original_create
                self._reusable_module._nc_createReusableInfo_patched = False
                logger.debug("createReusableInfo restored")
        except Exception as e:
            logger.debug("Failed to restore createReusableInfo: %s" % e)
        finally:
            self._reusable_module = None
            self._original_create = None

        self.on_avatar_become_non_player()
