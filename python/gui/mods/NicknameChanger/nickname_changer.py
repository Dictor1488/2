import BigWorld

from .identity import Identity
from .settings import settings
from .utils import logger, make_weak_callback

_MAX_PLAYER_NAME_RETRIES = 15
_RETRY_INTERVAL = 1.0


class NicknameChanger(object):

    def __init__(self):
        self.identity = Identity()
        self.session_provider = None
        self.items_cache = None

        self.controller = None
        self._player_name_retries = 0
        self._player_name_active = False
        self._player_name_generation = 0
        self._subscribed = False

        self._refresh_identity_from_settings()
        settings.subscribe(self._on_settings_changed)

    def _refresh_identity_from_settings(self):
        self.identity.update_replacement(settings.nickname, settings.clan_tag)

    def _on_settings_changed(self):
        self._refresh_identity_from_settings()
        if self.controller:
            self.controller.on_settings_changed()
        if self.identity.has_original:
            logger.debug("Replacement updated: %s [%s] -> %s [%s]" % (
                self.identity.original_name, self.identity.original_clan or "",
                self.identity.new_name, self.identity.new_clan or ""))

    def init(self):
        try:
            self._inject_dependencies()

            from .components import ComponentsController
            self.controller = ComponentsController(self.identity)

            self.controller.session_provider = self.session_provider
            self.controller.init()

            self._subscribe_player_events()
            logger.debug('NicknameChanger loaded')
        except Exception:
            logger.exception('NicknameChanger init failed')

    def fini(self):
        try:
            self._unsubscribe_player_events()
            if self.controller:
                self.controller.fini()
                self.controller = None
            self._player_name_generation += 1
            self._player_name_active = False
            logger.debug('NicknameChanger unloaded')
        except Exception:
            logger.exception('NicknameChanger fini failed')


    def _inject_dependencies(self):
        try:
            from helpers import dependency
            from skeletons.gui.battle_session import IBattleSessionProvider
            from skeletons.gui.shared import IItemsCache
            self.session_provider = dependency.instance(IBattleSessionProvider)
            self.items_cache = dependency.instance(IItemsCache)
            logger.debug("Dependencies injected")
        except Exception as e:
            logger.error("Dependency injection failed: %s" % e)


    def _subscribe_player_events(self):
        if self._subscribed:
            return
        try:
            from PlayerEvents import g_playerEvents
            g_playerEvents.onAccountBecomePlayer += self._on_account_become_player
            g_playerEvents.onAccountBecomeNonPlayer += self._on_account_become_non_player
            g_playerEvents.onAvatarBecomePlayer += self._on_avatar_become_player
            g_playerEvents.onAvatarReady += self._on_avatar_ready
            g_playerEvents.onAvatarBecomeNonPlayer += self._on_avatar_become_non_player
            self._subscribed = True
            logger.debug("Player events subscribed")
        except Exception as e:
            logger.error("Failed to subscribe player events: %s" % e)

    def _unsubscribe_player_events(self):
        if not self._subscribed:
            return
        try:
            from PlayerEvents import g_playerEvents
            g_playerEvents.onAccountBecomePlayer -= self._on_account_become_player
            g_playerEvents.onAccountBecomeNonPlayer -= self._on_account_become_non_player
            g_playerEvents.onAvatarBecomePlayer -= self._on_avatar_become_player
            g_playerEvents.onAvatarReady -= self._on_avatar_ready
            g_playerEvents.onAvatarBecomeNonPlayer -= self._on_avatar_become_non_player
        except Exception:
            pass
        self._subscribed = False


    def _on_account_become_player(self):
        try:
            self._discover_player_name()
            if self.controller:
                self.controller.on_lobby_ready()
        except Exception as e:
            logger.error("on_account_become_player: %s" % e)

    def _on_account_become_non_player(self):
        try:
            if self.controller:

                self.controller.on_avatar_become_non_player()
        except Exception as e:
            logger.error("on_account_become_non_player: %s" % e)

    def _on_avatar_become_player(self):
        if self.controller:
            self.controller.on_avatar_ready()

    def _on_avatar_ready(self):
        try:
            if self.controller:
                self.controller.on_avatar_ready()
        except Exception as e:
            logger.error("on_avatar_ready: %s" % e)

    def _on_avatar_become_non_player(self):
        try:
            if self.controller:
                self.controller.on_avatar_become_non_player()
                # Re-apply lobby hooks so battleResultsCache gets re-patched
                # when the post-battle results screen is shown in the lobby.
                self.controller.on_lobby_ready()
        except Exception as e:
            logger.error("on_avatar_become_non_player: %s" % e)


    def _discover_player_name(self):
        if self._player_name_active:
            return
        self._player_name_active = True
        self._player_name_retries = 0
        self._player_name_generation += 1
        self._try_get_name(self._player_name_generation)

    def _try_get_name(self, generation):
        if generation != self._player_name_generation:
            return
        if self.identity.has_original:
            self._player_name_active = False
            return
        try:
            player = BigWorld.player()
            if player and hasattr(player, 'name') and player.name:
                self.identity.original_name = player.name
                self._fetch_clan_tag()
                self._refresh_identity_from_settings()
                self._player_name_active = False
                logger.debug("Original: %s -> %s" % (self.identity.original_name, self.identity.new_name))
                if self.identity.new_clan:
                    logger.debug("Clan: %s -> %s" % (
                        self.identity.original_clan or "(none)", self.identity.new_clan))
                return
        except Exception as e:
            logger.debug("name lookup error: %s" % e)

        self._player_name_retries += 1
        if self._player_name_retries < _MAX_PLAYER_NAME_RETRIES:
            BigWorld.callback(_RETRY_INTERVAL, make_weak_callback(self, '_try_get_name', generation))
        else:
            logger.error("Failed to get player name after %d retries" % _MAX_PLAYER_NAME_RETRIES)
            self._player_name_active = False

    def _fetch_clan_tag(self):
        try:
            from gui.clans.clan_cache import g_clanCache
            if g_clanCache and g_clanCache.clanAbbrev:
                self.identity.original_clan = g_clanCache.clanAbbrev
                return
        except Exception:
            pass
        try:
            player = BigWorld.player()
            if player and hasattr(player, 'clanAbbrev'):
                self.identity.original_clan = player.clanAbbrev
        except Exception as e:
            logger.debug("clan tag fetch error: %s" % e)
