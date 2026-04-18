from ..settings import settings
from ..utils import logger, override, try_imports
from ..data_handlers import patch_vo_dict
from . import Component

_HIDDEN_ALIAS = u'???'
_HIDDEN_CLAN = u''


def _mask_vo(vo):
    """Replace any non-own player in a VO dict with ???."""
    if not isinstance(vo, dict):
        return vo
    uname = vo.get('userName', '') or vo.get('name', '')
    if uname:
        vo['userName'] = _HIDDEN_ALIAS
        vo['clanAbbrev'] = _HIDDEN_CLAN
        if 'fullName' in vo:
            vo['fullName'] = _HIDDEN_ALIAS
        if 'name' in vo:
            vo['name'] = _HIDDEN_ALIAS
    return vo


class LobbyPrbComponent(Component):

    def setup_hooks(self):
        identity = self.identity

        PreQueueEntity = try_imports(
            lambda: __import__('gui.prb_control.entities.base.pre_queue.entity', fromlist=['PreQueueEntity']).PreQueueEntity,
            lambda: __import__('gui.prb_control.entities.base', fromlist=['PreQueueEntity']).PreQueueEntity,
        )
        if PreQueueEntity and hasattr(PreQueueEntity, '_makePlayerVO'):
            @override(PreQueueEntity, '_makePlayerVO')
            def hooked_pq_make_vo(baseMethod, baseObject, *args, **kwargs):
                vo = baseMethod(baseObject, *args, **kwargs)
                if not settings.enabled or not identity.has_original:
                    return vo
                vo = patch_vo_dict(vo, identity)
                # hide_all for other players already handled inside patch_vo_dict
                return vo

        BasePrbEntity = try_imports(
            lambda: __import__('gui.prb_control.entities.base.entity', fromlist=['BasePrbEntity']).BasePrbEntity,
            lambda: __import__('gui.prb_control.entities', fromlist=['BasePrbEntity']).BasePrbEntity,
        )
        if BasePrbEntity and hasattr(BasePrbEntity, '_makePlayerVO'):
            @override(BasePrbEntity, '_makePlayerVO')
            def hooked_base_make_vo(baseMethod, baseObject, *args, **kwargs):
                vo = baseMethod(baseObject, *args, **kwargs)
                if not settings.enabled or not identity.has_original:
                    return vo
                return patch_vo_dict(vo, identity)

        StrongholdEntity = try_imports(
            lambda: getattr(__import__('gui.prb_control.entities.stronghold', fromlist=['stronghold']), 'StrongholdEntity', None),
            lambda: __import__('gui.prb_control.entities.fortifications', fromlist=['StrongholdEntity']).StrongholdEntity,
        )
        if StrongholdEntity and hasattr(StrongholdEntity, '_makePlayerVO'):
            @override(StrongholdEntity, '_makePlayerVO')
            def hooked_sh_make_vo(baseMethod, baseObject, *args, **kwargs):
                vo = baseMethod(baseObject, *args, **kwargs)
                if not settings.enabled or not identity.has_original:
                    return vo
                return patch_vo_dict(vo, identity)

        try:
            from battle_royale.gui.impl.lobby.views.pre_battle import PreBattleView
        except ImportError:
            logger.debug("Battle Royale PreBattleView not available")
            return

        priv = '_PreBattleView__convertToPlayers'
        if hasattr(PreBattleView, priv):
            @override(PreBattleView, priv)
            def hooked_br_convert(baseMethod, baseObject, participants):
                teams = baseMethod(baseObject, participants)
                if not settings.enabled or not identity.has_original:
                    return teams
                hide_all = settings.hide_all_nicknames
                for teamID, players in teams.items():
                    for player in players:
                        pname = player.get('name', '')
                        if pname == identity.original_name:
                            player['name'] = identity.new_name
                            if identity.new_clan and 'clanAbbrev' in player:
                                player['clanAbbrev'] = identity.new_clan
                        elif hide_all and pname:
                            player['name'] = _HIDDEN_ALIAS
                            if 'clanAbbrev' in player:
                                player['clanAbbrev'] = _HIDDEN_CLAN
                return teams
