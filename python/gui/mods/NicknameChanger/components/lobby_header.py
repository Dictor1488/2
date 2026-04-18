import weakref

from ..settings import settings
from ..utils import logger, override
from . import Component


class LobbyHeaderComponent(Component):

    def __init__(self, controller):
        super(LobbyHeaderComponent, self).__init__(controller)
        self._lc_original = None
        self._lc_ctx = None
        self._presenter_ref = None

    def setup_hooks(self):
        try:
            from gui.impl.lobby.page.user_account_presenter import UserAccountPresenter
        except ImportError:
            logger.debug("UserAccountPresenter not available")
            return

        identity = self.identity
        comp = self

        if hasattr(UserAccountPresenter, '_prepareChildren'):
            @override(UserAccountPresenter, '_prepareChildren')
            def hooked_prepare(baseMethod, baseObject, *args, **kwargs):
                comp._presenter_ref = weakref.ref(baseObject)
                return baseMethod(baseObject, *args, **kwargs)

        update_user = '_UserAccountPresenter__updateUserInfo'
        if hasattr(UserAccountPresenter, update_user):
            @override(UserAccountPresenter, update_user)
            def hooked_update_user(baseMethod, baseObject):
                baseMethod(baseObject)
                comp._presenter_ref = weakref.ref(baseObject)
                if not settings.enabled or not identity.has_original:
                    return
                try:
                    with baseObject.viewModel.userInfo.transaction() as model:
                        model.setUserName(identity.new_name)
                except Exception as e:
                    logger.debug("UserAccountPresenter user info patch error: %s" % e)

        update_clan = '_UserAccountPresenter__updateClanInfo'
        if hasattr(UserAccountPresenter, update_clan):
            @override(UserAccountPresenter, update_clan)
            def hooked_update_clan(baseMethod, baseObject, *args, **kwargs):
                baseMethod(baseObject, *args, **kwargs)
                if not settings.enabled or not identity.has_original or not identity.new_clan:
                    return
                try:
                    with baseObject.viewModel.userInfo.transaction() as model:
                        model.setClanAbbrev(identity.new_clan)
                        model.setIsInClan(True)
                except Exception as e:
                    logger.debug("UserAccountPresenter clan info patch error: %s" % e)

        try:
            from gui.shared.personality import ServicesLocator
            ctx = ServicesLocator.lobbyContext
            original = ctx.getPlayerFullName

            def patched(pName, clanInfo=None, clanAbbrev=None, regionCode=None, pDBID=None, **kwargs):
                if settings.enabled and identity.has_original and pName == identity.original_name:
                    if identity.new_clan:
                        clanAbbrev = identity.new_clan
                    return original(identity.new_name, clanInfo, clanAbbrev, regionCode, pDBID, **kwargs)
                return original(pName, clanInfo, clanAbbrev, regionCode, pDBID, **kwargs)

            self._lc_original = original
            self._lc_ctx = ctx
            ctx.getPlayerFullName = patched
            logger.debug("lobbyContext.getPlayerFullName hooked")
        except Exception as e:
            logger.error("Failed to hook lobbyContext.getPlayerFullName: %s" % e)
            self._lc_original = None
            self._lc_ctx = None

    def on_settings_changed(self):
        if self._presenter_ref is None:
            return
        presenter = self._presenter_ref()
        if presenter is None:
            return
        try:
            self._apply_to_presenter(presenter)
        except Exception as e:
            logger.debug("on_settings_changed apply failed: %s" % e)

    def _apply_to_presenter(self, presenter):
        identity = self.identity
        with presenter.viewModel.userInfo.transaction() as model:
            if settings.enabled and identity.has_original:
                model.setUserName(identity.new_name)
                if identity.new_clan:
                    model.setClanAbbrev(identity.new_clan)
                    model.setIsInClan(True)
            else:
                if identity.original_name:
                    model.setUserName(identity.original_name)
                if identity.original_clan is not None:
                    model.setClanAbbrev(identity.original_clan or '')
                    model.setIsInClan(bool(identity.original_clan))

    def fini(self):
        try:
            if self._lc_ctx is not None and self._lc_original is not None:
                self._lc_ctx.getPlayerFullName = self._lc_original
                logger.debug("lobbyContext.getPlayerFullName restored")
        except Exception as e:
            logger.debug("Failed to restore lobbyContext: %s" % e)
        finally:
            self._lc_ctx = None
            self._lc_original = None
            self._presenter_ref = None
