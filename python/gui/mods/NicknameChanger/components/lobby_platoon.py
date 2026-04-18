from ..settings import settings
from ..utils import logger, override
from ..platoon_tracker import platoon_tracker
from . import Component

try:
    unicode
except NameError:
    unicode = str

_HIDDEN_ALIAS = u'???'
_HIDDEN_CLAN = u''


class LobbyPlatoonComponent(Component):

    def setup_hooks(self):
        try:
            from gui.impl.lobby.platoon.view.platoon_members_view import SquadMembersView
        except ImportError:
            logger.debug("SquadMembersView not available")
            return

        identity = self.identity

        @override(SquadMembersView, '_setPlayerData')
        def hooked_set_player_data(baseMethod, baseObject, accID, isWTREnabled, slotData, playerData, slotModel):
            if settings.enabled and identity.has_original:
                user_name = playerData.get('userName', '')

                if user_name == identity.original_name:
                    playerData['userName'] = identity.new_name
                    if identity.new_clan:
                        playerData['clanAbbrev'] = identity.new_clan

                elif platoon_tracker.is_platoon_mate(user_name):
                    alias = platoon_tracker.get_alias(user_name)
                    playerData['userName'] = alias
                    playerData['clanAbbrev'] = _HIDDEN_CLAN
                    playerData['fullName'] = alias

                elif settings.hide_all_nicknames and user_name:
                    playerData['userName'] = _HIDDEN_ALIAS
                    playerData['clanAbbrev'] = _HIDDEN_CLAN
                    playerData['fullName'] = _HIDDEN_ALIAS

            return baseMethod(baseObject, accID, isWTREnabled, slotData, playerData, slotModel)

        if hasattr(SquadMembersView, '_populate'):
            @override(SquadMembersView, '_populate')
            def hooked_populate(baseMethod, baseObject, *args, **kwargs):
                result = baseMethod(baseObject, *args, **kwargs)
                if settings.enabled and identity.has_original:
                    _refresh_platoon_from_squad_view(baseObject, identity.original_name)
                return result

        if hasattr(SquadMembersView, '_update'):
            @override(SquadMembersView, '_update')
            def hooked_update(baseMethod, baseObject, *args, **kwargs):
                result = baseMethod(baseObject, *args, **kwargs)
                if settings.enabled and identity.has_original:
                    _refresh_platoon_from_squad_view(baseObject, identity.original_name)
                return result

    def on_lobby_ready(self):
        platoon_tracker.reset()

    def on_avatar_become_non_player(self):
        platoon_tracker.reset()


def _refresh_platoon_from_squad_view(view, own_name):
    try:
        from gui.impl.lobby.platoon.platoon_helpers import g_platoonCtrl
        if g_platoonCtrl and hasattr(g_platoonCtrl, 'getMembers'):
            members = g_platoonCtrl.getMembers()
            if members:
                platoon_tracker.update_from_members(members, own_name=own_name)
                return
    except Exception:
        pass

    try:
        for attr in ('_members', '_slots', '_playerItems'):
            raw = getattr(view, attr, None)
            if raw:
                platoon_tracker.update_from_members(raw, own_name=own_name)
                return
    except Exception as e:
        logger.debug("_refresh_platoon_from_squad_view error: %s" % e)
