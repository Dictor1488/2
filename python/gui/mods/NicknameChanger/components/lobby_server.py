# -*- coding: utf-8 -*-
"""
LobbyServerComponent
Hides the server/cluster name in the hangar:
  - Bottom bar  "EU2 III"  (ServerInfoPresenter / UserAccountPresenter)
  - Ping dropdown header   "WOT EU2"  (ServerSelectorPresenter / PingPresenter)
"""

from ..settings import settings
from ..utils import logger, override
from . import Component


class LobbyServerComponent(Component):

    def setup_hooks(self):
        self._hook_server_info_presenter()
        self._hook_user_account_server()
        self._hook_ping_presenter()
        self._hook_server_selector()

    # ------------------------------------------------------------------
    # 1. ServerInfoPresenter  (bottom-left "EU2 III" bar, newer clients)
    # ------------------------------------------------------------------
    def _hook_server_info_presenter(self):
        presenter_cls = None
        for path in (
            'gui.impl.lobby.server_info.server_info_presenter',
            'gui.impl.lobby.header.server_info_presenter',
            'gui.impl.lobby.page.server_info_presenter',
        ):
            try:
                import importlib
                mod = importlib.import_module(path)
                for attr in dir(mod):
                    if 'server' in attr.lower() and 'presenter' in attr.lower():
                        presenter_cls = getattr(mod, attr)
                        break
                if presenter_cls:
                    break
            except ImportError:
                continue

        if presenter_cls is None:
            logger.debug("ServerInfoPresenter not found")
            return

        for method_name in (
            '_updateServerInfo',
            '__updateServerInfo',
            '_ServerInfoPresenter__updateServerInfo',
            '_update',
            'update',
        ):
            if not hasattr(presenter_cls, method_name):
                continue

            @override(presenter_cls, method_name)
            def hooked_server_info(baseMethod, baseObject, *args, **kwargs):
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
                                       'setServerLabel', 'setName'):
                            if hasattr(model, setter):
                                getattr(model, setter)(u'')
                except Exception as e:
                    logger.debug("ServerInfoPresenter hook error: %s" % e)

            logger.debug("ServerInfoPresenter.%s hooked" % method_name)
            break

    # ------------------------------------------------------------------
    # 2. UserAccountPresenter — __updateServerInfo  (header bar)
    # ------------------------------------------------------------------
    def _hook_user_account_server(self):
        try:
            from gui.impl.lobby.page.user_account_presenter import UserAccountPresenter
        except ImportError:
            logger.debug("UserAccountPresenter not available for server hook")
            return

        method_name = '_UserAccountPresenter__updateServerInfo'
        if not hasattr(UserAccountPresenter, method_name):
            # try without mangling
            for candidate in ('_updateServerInfo', 'updateServerInfo'):
                if hasattr(UserAccountPresenter, candidate):
                    method_name = candidate
                    break
            else:
                logger.debug("UserAccountPresenter has no updateServerInfo method")
                return

        @override(UserAccountPresenter, method_name)
        def hooked_uap_server(baseMethod, baseObject, *args, **kwargs):
            baseMethod(baseObject, *args, **kwargs)
            if not settings.enabled or not settings.hide_server:
                return
            try:
                vm = getattr(baseObject, 'viewModel', None)
                if vm is None:
                    return
                info = getattr(vm, 'userInfo', vm)
                with info.transaction() as model:
                    for setter in ('setServerName', 'setServer', 'setClusterName',
                                   'setClusterId', 'setClusterID', 'setRegionTag'):
                        if hasattr(model, setter):
                            getattr(model, setter)(u'')
            except Exception as e:
                logger.debug("UserAccountPresenter server hook error: %s" % e)

        logger.debug("UserAccountPresenter.%s hooked" % method_name)

    # ------------------------------------------------------------------
    # 3. PingPresenter / ServerPingPresenter  (ping dropdown)
    # ------------------------------------------------------------------
    def _hook_ping_presenter(self):
        presenter_cls = None
        for path in (
            'gui.impl.lobby.ping.ping_presenter',
            'gui.impl.lobby.server_ping.server_ping_presenter',
            'gui.impl.lobby.header.ping_presenter',
        ):
            try:
                import importlib
                mod = importlib.import_module(path)
                for attr in dir(mod):
                    if 'ping' in attr.lower() and 'presenter' in attr.lower():
                        presenter_cls = getattr(mod, attr)
                        break
                if presenter_cls:
                    break
            except ImportError:
                continue

        if presenter_cls is None:
            logger.debug("PingPresenter not found")
            return

        for method_name in ('_updateServers', '_update', 'update', '_updateServerList'):
            if not hasattr(presenter_cls, method_name):
                continue

            @override(presenter_cls, method_name)
            def hooked_ping(baseMethod, baseObject, *args, **kwargs):
                baseMethod(baseObject, *args, **kwargs)
                if not settings.enabled or not settings.hide_server:
                    return
                try:
                    vm = getattr(baseObject, 'viewModel', None)
                    if vm is None:
                        return
                    with vm.transaction() as model:
                        if hasattr(model, 'setServerName'):
                            model.setServerName(u'')
                        if hasattr(model, 'setCurrentServerName'):
                            model.setCurrentServerName(u'')
                except Exception as e:
                    logger.debug("PingPresenter hook error: %s" % e)

            logger.debug("PingPresenter.%s hooked" % method_name)
            break

    # ------------------------------------------------------------------
    # 4. ServerSelectorPresenter  (server picker dropdown)
    # ------------------------------------------------------------------
    def _hook_server_selector(self):
        presenter_cls = None
        for path in (
            'gui.impl.lobby.server_selector.server_selector_presenter',
            'gui.impl.lobby.header.server_selector_presenter',
            'gui.impl.lobby.ping.server_selector_presenter',
        ):
            try:
                import importlib
                mod = importlib.import_module(path)
                for attr in dir(mod):
                    if 'selector' in attr.lower() and 'presenter' in attr.lower():
                        presenter_cls = getattr(mod, attr)
                        break
                if presenter_cls:
                    break
            except ImportError:
                continue

        if presenter_cls is None:
            logger.debug("ServerSelectorPresenter not found")
            return

        for method_name in ('_updateCurrentServer', '_updateServer', '_update', 'update'):
            if not hasattr(presenter_cls, method_name):
                continue

            @override(presenter_cls, method_name)
            def hooked_selector(baseMethod, baseObject, *args, **kwargs):
                baseMethod(baseObject, *args, **kwargs)
                if not settings.enabled or not settings.hide_server:
                    return
                try:
                    vm = getattr(baseObject, 'viewModel', None)
                    if vm is None:
                        return
                    with vm.transaction() as model:
                        for setter in ('setCurrentServerName', 'setServerName',
                                       'setSelectedServer', 'setName'):
                            if hasattr(model, setter):
                                getattr(model, setter)(u'')
                except Exception as e:
                    logger.debug("ServerSelectorPresenter hook error: %s" % e)

            logger.debug("ServerSelectorPresenter.%s hooked" % method_name)
            break
