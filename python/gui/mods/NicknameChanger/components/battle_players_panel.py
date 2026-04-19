# -*- coding: utf-8 -*-

from ..settings import settings
from ..utils import logger, override, try_imports
from ..platoon_tracker import platoon_tracker
from . import Component

_HIDDEN_CLAN = u''


def _strip_badges(item):
    if not isinstance(item, dict):
        return

    for key in list(item.keys()):
        low = key.lower()
        if (
            'badge' in low or
            'dogtag' in low or
            'insign' in low or
            'patch' in low or
            'emblem' in low
        ):
            val = item.get(key)
            if isinstance(val, list):
                item[key] = []
            elif isinstance(val, dict):
                item[key] = {}
            else:
                item[key] = None


class BattlePlayersPanelComponent(Component):

    def __init__(self, controller):
        super(BattlePlayersPanelComponent, self).__init__(controller)
        self._aliases = {}
        self._next_alias = 1

    def _get_hidden_alias(self, item):
        key = (
            item.get('vehicleID') or
            item.get('vehID') or
            item.get('accountDBID') or
            item.get('dbID') or
            item.get('userName') or
            item.get('playerName')
        )

        alias = self._aliases.get(key)
        if alias is None:
            alias = u'Player %d' % self._next_alias
            self._aliases[key] = alias
            self._next_alias += 1
        return alias

    def _is_own_row(self, item, identity):
        try:
            import BigWorld
            player = BigWorld.player()
            my_vehicle_id = getattr(player, 'playerVehicleID', None)
        except Exception:
            my_vehicle_id = None

        uname = item.get('userName', '')
        if uname and (uname == identity.original_name or uname == identity.new_name):
            return True

        if item.get('isCurrentPlayer') is True:
            return True

        for key in ('vehicleID', 'vehID'):
            if my_vehicle_id is not None and item.get(key) == my_vehicle_id:
                return True

        return False

    def setup_hooks(self):
        PlayersPanel = try_imports(
            lambda: __import__('gui.Scaleform.daapi.view.battle.shared.players_panel', fromlist=['PlayersPanel']).PlayersPanel,
            lambda: __import__('gui.Scaleform.daapi.view.battle.classic.players_panel', fromlist=['PlayersPanel']).PlayersPanel,
        )

        if PlayersPanel is None or not hasattr(PlayersPanel, '_makeVO'):
            logger.debug("PlayersPanel._makeVO not available")
            return

        identity = self.identity

        @override(PlayersPanel, '_makeVO')
        def hooked_make_vo(baseMethod, baseObject, *args, **kwargs):
            result = baseMethod(baseObject, *args, **kwargs)

            if not settings.enabled or not identity.has_original:
                return result

            hide_all = settings.hide_all_nicknames

            if isinstance(result, dict):
                for key in ('leftScope', 'rightScope', 'left', 'right'):
                    items = result.get(key)
                    if not isinstance(items, (list, tuple)):
                        continue

                    for item in items:
                        if not isinstance(item, dict):
                            continue

                        uname = item.get('userName', '')
                        _strip_badges(item)

                        if self._is_own_row(item, identity):
                            item['userName'] = identity.new_name
                            item['displayName'] = identity.new_name
                            item['fullName'] = identity.new_name
                            if identity.new_clan:
                                item['clanAbbrev'] = identity.new_clan

                        elif uname and platoon_tracker.is_platoon_mate(uname):
                            alias = platoon_tracker.get_alias(uname)
                            item['userName'] = alias
                            item['displayName'] = alias
                            item['fullName'] = alias
                            item['clanAbbrev'] = _HIDDEN_CLAN

                        elif hide_all:
                            alias = self._get_hidden_alias(item)
                            item['userName'] = alias
                            item['displayName'] = alias
                            item['fullName'] = alias
                            item['clanAbbrev'] = _HIDDEN_CLAN

            return result
