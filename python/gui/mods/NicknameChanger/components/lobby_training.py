from ..settings import settings
from ..utils import logger, override, try_imports, format_full_name
from . import Component

_HIDDEN_ALIAS = u'???'
_HIDDEN_CLAN = u''


class LobbyTrainingComponent(Component):

    def setup_hooks(self):
        TrainingRoomBase = try_imports(
            lambda: __import__('gui.Scaleform.daapi.view.lobby.trainings.TrainingRoomBase', fromlist=['TrainingRoomBase']).TrainingRoomBase,
        )
        if TrainingRoomBase is None:
            logger.debug("TrainingRoomBase not available")
            return

        identity = self.identity

        if hasattr(TrainingRoomBase, '_makeAccountsData'):
            @override(TrainingRoomBase, '_makeAccountsData')
            def hooked_make_accounts(baseMethod, baseObject, accounts, rLabel=None):
                result = baseMethod(baseObject, accounts, rLabel)
                if not settings.enabled or not identity.has_original:
                    return result
                hide_all = settings.hide_all_nicknames
                if result and 'listData' in result:
                    for vo in result['listData']:
                        uname = vo.get('userName', '')
                        if uname == identity.original_name:
                            vo['userName'] = identity.new_name
                            if identity.new_clan:
                                vo['clanAbbrev'] = identity.new_clan
                            clan = identity.new_clan or vo.get('clanAbbrev', '')
                            vo['fullName'] = format_full_name(identity.new_name, clan)
                        elif hide_all and uname:
                            vo['userName'] = _HIDDEN_ALIAS
                            vo['clanAbbrev'] = _HIDDEN_CLAN
                            vo['fullName'] = _HIDDEN_ALIAS
                return result

        show_settings_attr = '_TrainingRoomBase__showSettings'
        if hasattr(TrainingRoomBase, show_settings_attr):
            @override(TrainingRoomBase, show_settings_attr)
            def hooked_show_settings(baseMethod, baseObject, entity):
                baseMethod(baseObject, entity)
                if not settings.enabled or not identity.has_original:
                    return
                try:
                    s = entity.getSettings()
                    if s and s['creator'] == identity.original_name:
                        info = {'creator': identity.new_name}
                        if identity.new_clan:
                            info['creatorClan'] = identity.new_clan
                        info['creatorFullName'] = format_full_name(
                            identity.new_name, identity.new_clan)
                        baseObject.as_setInfoS(info)
                except Exception as e:
                    logger.debug("training __showSettings patch error: %s" % e)
