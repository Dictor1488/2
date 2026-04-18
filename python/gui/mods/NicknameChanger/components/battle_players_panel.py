from ..settings import settings
from ..utils import logger, override, try_imports
from ..platoon_tracker import platoon_tracker
from . import Component

_HIDDEN_ALIAS = u'???'
_HIDDEN_CLAN = u''


class BattlePlayersPanelComponent(Component):

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
                    if isinstance(items, (list, tuple)):
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            uname = item.get('userName', '')
                            if uname == identity.original_name:
                                item['userName'] = identity.new_name
                                if identity.new_clan:
                                    item['clanAbbrev'] = identity.new_clan
                            elif platoon_tracker.is_platoon_mate(uname):
                                alias = platoon_tracker.get_alias(uname)
                                item['userName'] = alias
                                item['clanAbbrev'] = _HIDDEN_CLAN
                            elif hide_all and uname:
                                item['userName'] = _HIDDEN_ALIAS
                                item['clanAbbrev'] = _HIDDEN_CLAN
            return result
