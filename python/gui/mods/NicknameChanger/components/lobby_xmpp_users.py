from ..settings import settings
from ..utils import logger, override
from . import Component


class LobbyXmppUsersComponent(Component):

    def setup_hooks(self):
        identity = self.identity

        try:
            from messenger.storage.UsersStorage import UsersStorage
            from messenger.proto.xmpp.entities import XMPPUserEntity
        except ImportError:
            logger.debug("UsersStorage / XMPPUserEntity not available")
            return

        def anonymize_user(user):
            if not isinstance(user, XMPPUserEntity):
                return
            try:
                current_name = user.getName() if hasattr(user, 'getName') else None
                if current_name != identity.original_name:
                    return
                try:
                    user._name = identity.new_name
                except (AttributeError, TypeError):
                    pass
                if identity.new_clan:
                    try:
                        if hasattr(user, '_clanInfo') and user._clanInfo is not None:
                            user._clanInfo.abbrev = identity.new_clan
                    except (AttributeError, TypeError):
                        pass
            except Exception as e:
                logger.debug("anonymize_user error: %s" % e)

        if hasattr(UsersStorage, 'addUser'):
            @override(UsersStorage, 'addUser')
            def hooked_add_user(baseMethod, baseObject, user):
                if settings.enabled and identity.has_original:
                    anonymize_user(user)
                return baseMethod(baseObject, user)

        if hasattr(UsersStorage, 'setUser'):
            @override(UsersStorage, 'setUser')
            def hooked_set_user(baseMethod, baseObject, user):
                if settings.enabled and identity.has_original:
                    anonymize_user(user)
                return baseMethod(baseObject, user)

        if hasattr(UsersStorage, 'getUser'):
            @override(UsersStorage, 'getUser')
            def hooked_get_user(baseMethod, baseObject, *args, **kwargs):
                user = baseMethod(baseObject, *args, **kwargs)
                if settings.enabled and identity.has_original:
                    anonymize_user(user)
                return user

        try:
            from messenger.gui.Scaleform.data.contacts_data_provider import ContactsDataProvider
        except ImportError:
            logger.debug("ContactsDataProvider not available")
            return

        priv = '_ContactsDataProvider__updateCollection'
        if hasattr(ContactsDataProvider, priv):
            @override(ContactsDataProvider, priv)
            def hooked_update_collection(baseMethod, baseObject, targetList):
                if settings.enabled and identity.has_original:
                    try:
                        for listPart in targetList:
                            for child in listPart.get('children', []):
                                _fix_child_clantag(child, identity)
                                _fix_child_player(child, identity)
                                for sub in child.get('children', []):
                                    _fix_child_player(sub, identity)
                                    for sub2 in sub.get('children', []):
                                        _fix_child_player(sub2, identity)
                    except Exception as e:
                        logger.debug("contacts update patch error: %s" % e)
                return baseMethod(baseObject, targetList)


def _fix_child_clantag(child, identity):
    try:
        if not identity.original_clan:
            return
        if not identity.new_clan:
            return
        mask = '[%s]' % identity.original_clan
        new_mask = '[%s]' % identity.new_clan
        data = child.get('data', {})
        for key in ('headerTitle', 'headerDisplayTitle'):
            value = data.get(key, '')
            if mask in value:
                data[key] = value.replace(mask, new_mask)
    except Exception:
        pass


def _fix_child_player(child, identity):
    try:
        data = child.get('data', {})
        user_props = data.get('userProps', {})
        if 'userName' not in user_props:
            return
        if user_props['userName'] != identity.original_name:
            return
        user_props['userName'] = identity.new_name
        if identity.new_clan and 'clanAbbrev' in user_props:
            user_props['clanAbbrev'] = identity.new_clan
        child['criteria'] = (1, identity.new_name)
    except Exception:
        pass
