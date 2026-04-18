from ..utils import logger, restore_overrides


class Component(object):

    def __init__(self, controller):
        self.controller = controller
        self.identity = controller.identity

    def setup_hooks(self):
        """Override: install @override-decorated wrappers."""
        pass

    def fini(self):
        """Override to restore non-override state (event subs, attr patches)."""
        pass

    def on_lobby_ready(self):
        pass

    def on_avatar_ready(self):
        pass

    def on_avatar_become_non_player(self):
        pass

    def on_settings_changed(self):
        pass


class ComponentsController(object):

    def __init__(self, identity):
        self.identity = identity
        self.components = []
        self._initialized = False

    def init(self):
        if self._initialized:
            return
        self._initialized = True

        from .lobby_header import LobbyHeaderComponent
        from .lobby_platoon import LobbyPlatoonComponent
        from .lobby_stronghold import LobbyStrongholdComponent
        from .lobby_training import LobbyTrainingComponent
        from .lobby_clan_chat import LobbyClanChatComponent
        from .lobby_xmpp_users import LobbyXmppUsersComponent
        from .lobby_prb import LobbyPrbComponent
        from .battle_arena import BattleArenaComponent
        from .battle_players_panel import BattlePlayersPanelComponent
        from .battle_full_stats import BattleFullStatsComponent
        from .battle_results import BattleResultsComponent

        component_classes = [
            LobbyHeaderComponent,
            LobbyPlatoonComponent,
            LobbyStrongholdComponent,
            LobbyTrainingComponent,
            LobbyClanChatComponent,
            LobbyXmppUsersComponent,
            LobbyPrbComponent,
            BattleArenaComponent,
            BattlePlayersPanelComponent,
            BattleFullStatsComponent,
            BattleResultsComponent,
        ]

        for cls in component_classes:
            try:
                comp = cls(self)
                comp.setup_hooks()
                self.components.append(comp)
                logger.debug("Component %s initialized" % cls.__name__)
            except Exception as e:
                logger.error("Failed to init component %s: %s" % (cls.__name__, e))

        logger.debug("Components initialized: %d" % len(self.components))

    def fini(self):
        for comp in self.components:
            try:
                comp.fini()
            except Exception as e:
                logger.error("fini failed for %s: %s" % (type(comp).__name__, e))
        restore_overrides()
        self.components = []
        self._initialized = False

    def on_lobby_ready(self):
        for comp in self.components:
            try:
                comp.on_lobby_ready()
            except Exception as e:
                logger.error("on_lobby_ready failed for %s: %s" % (
                    type(comp).__name__, e))

    def on_avatar_ready(self):
        for comp in self.components:
            try:
                comp.on_avatar_ready()
            except Exception as e:
                logger.error("on_avatar_ready failed for %s: %s" % (
                    type(comp).__name__, e))

    def on_avatar_become_non_player(self):
        for comp in self.components:
            try:
                comp.on_avatar_become_non_player()
            except Exception as e:
                logger.error("on_avatar_become_non_player failed for %s: %s" % (
                    type(comp).__name__, e))

    def on_settings_changed(self):
        for comp in self.components:
            try:
                comp.on_settings_changed()
            except Exception as e:
                logger.error("on_settings_changed failed for %s: %s" % (
                    type(comp).__name__, e))
