# -*- coding: utf-8 -*-
"""
BattleServerComponent
Hides the server/cluster label displayed during battle
(e.g. "EU2 III" shown in the bottom bar in battle HUD).
"""

from ..settings import settings
from ..utils import logger, override
from . import Component


class BattleServerComponent(Component):

    def setup_hooks(self):
        self._hook_battle_server_info()
        self._hook_battle_loading_info()

    def _hook_battle_server_info(self):
        presenter_cls = None
        for path in (
            'gui.impl.battle.server_info.server_info_presenter',
            'gui.impl.battle.screen.server_info_presenter',
            'gui.impl.battle.shared.server_info_presenter',
            'gui.impl.battle.battle_loading.battle_loading_presenter',
        ):
            try:
                import importlib
                mod = importlib.import_module(path)
                for attr in dir(mod):
                    obj = getattr(mod, attr, None)
                    if obj and isinstance(obj, type) and 'presenter' in attr.lower():
                        presenter_cls = obj
                        break
                if presenter_cls:
                    break
            except ImportError:
                continue

        if presenter_cls is None:
            logger.debug("BattleServerInfoPresenter not found")
            return

        for method_name in ('_updateServerInfo', '__updateServerInfo', '_update', 'update'):
            if not hasattr(presenter_cls, method_name):
                continue

            @override(presenter_cls, method_name)
            def hooked_battle_server(baseMethod, baseObject, *args, **kwargs):
                baseMethod(baseObject, *args, **kwargs)
                if not settings.enabled or not settings.hide_server:
                    return
                try:
                    vm = getattr(baseObject, 'viewModel', None)
                    if vm is None:
                        return
                    with vm.transaction() as model:
                        for setter in ('setServerName', 'setServer', 'setClusterName',
                                       'setClusterId', 'setClusterID', 'setRegionTag',
                                       'setServerLabel'):
                            if hasattr(model, setter):
                                getattr(model, setter)(u'')
                except Exception as e:
                    logger.debug("BattleServerInfoPresenter hook error: %s" % e)

            logger.debug("BattleServerInfo.%s hooked" % method_name)
            break

    def _hook_battle_loading_info(self):
        """Hook battle loading screen which also shows server name."""
        for path, attr_hint in (
            ('gui.impl.battle.battle_loading.battle_loading_presenter', 'loading'),
            ('gui.impl.battle.screen.battle_screen_presenter', 'screen'),
        ):
            try:
                import importlib
                mod = importlib.import_module(path)
                for attr in dir(mod):
                    obj = getattr(mod, attr, None)
                    if obj and isinstance(obj, type) and 'presenter' in attr.lower():
                        for method_name in ('_updateServerInfo', '_setServerInfo',
                                            '__updateServerInfo', '_update'):
                            if not hasattr(obj, method_name):
                                continue

                            @override(obj, method_name)
                            def hooked_loading(baseMethod, baseObject, *args, **kwargs):
                                baseMethod(baseObject, *args, **kwargs)
                                if not settings.enabled or not settings.hide_server:
                                    return
                                try:
                                    vm = getattr(baseObject, 'viewModel', None)
                                    if vm is None:
                                        return
                                    with vm.transaction() as model:
                                        for setter in ('setServerName', 'setServer',
                                                       'setClusterName', 'setClusterId',
                                                       'setClusterID', 'setRegionTag'):
                                            if hasattr(model, setter):
                                                getattr(model, setter)(u'')
                                except Exception as e:
                                    logger.debug("BattleLoadingServer hook error: %s" % e)

                            logger.debug("%s.%s hooked for server hide" % (attr, method_name))
                            break
            except ImportError:
                continue
