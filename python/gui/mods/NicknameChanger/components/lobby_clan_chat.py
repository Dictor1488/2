from ..settings import settings
from ..utils import logger, override
from . import Component


class LobbyClanChatComponent(Component):

    def setup_hooks(self):
        identity = self.identity

        try:
            from messenger.proto.xmpp.entities import XmppClanChannelEntity
        except ImportError:
            logger.debug("XmppClanChannelEntity not available")
            return

        @override(XmppClanChannelEntity, '__init__')
        def hooked_init(baseMethod, baseObject, dbID=0, clanTag=''):
            if settings.enabled and identity.new_clan and clanTag:
                clanTag = identity.new_clan
            return baseMethod(baseObject, dbID, clanTag)

        try:
            from messenger.proto.xmpp.xmpp_clan_listener import XmppClanListener
        except ImportError:
            logger.debug("XmppClanListener not available")
            return

        priv = '_XmppClanListener__addClanChannelToStorage'
        abbrev_attr = '_XmppClanListener__clanAbbrev'
        if hasattr(XmppClanListener, priv):
            @override(XmppClanListener, priv)
            def hooked_add_channel(baseMethod, baseObject):
                if settings.enabled and identity.new_clan and hasattr(baseObject, abbrev_attr):
                    backup = getattr(baseObject, abbrev_attr)
                    setattr(baseObject, abbrev_attr, identity.new_clan)
                    try:
                        return baseMethod(baseObject)
                    finally:
                        setattr(baseObject, abbrev_attr, backup)
                return baseMethod(baseObject)

    def on_lobby_ready(self):
        self._rename_existing_channel()

    def on_settings_changed(self):
        self._rename_existing_channel()

    def _rename_existing_channel(self):
        try:
            from messenger.proto.xmpp.find_criteria import XmppClanChannelCriteria
            from messenger.storage import storage_getter, StorageDecorator

            class _Accessor(StorageDecorator):
                @storage_getter('channels')
                def channelsStorage(self):
                    return

            accessor = _Accessor()
            channels_storage = accessor.channelsStorage
            if not channels_storage:
                return
            criteria = XmppClanChannelCriteria()
            for channel in channels_storage.getChannelsByCriteria(criteria):
                if hasattr(channel, 'isClan') and channel.isClan() and hasattr(channel, 'setName'):
                    if settings.enabled and self.identity.new_clan:
                        new_name = '[%s]' % self.identity.new_clan
                    elif self.identity.original_clan:
                        new_name = '[%s]' % self.identity.original_clan
                    else:
                        continue
                    if channel.getName() != new_name:
                        channel.setName(new_name)
                        logger.debug("Renamed clan channel -> %s" % new_name)
        except Exception as e:
            logger.debug("clan channel rename failed: %s" % e)
