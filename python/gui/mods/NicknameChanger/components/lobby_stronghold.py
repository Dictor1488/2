import re

from ..settings import settings
from ..utils import logger, override, try_imports, replace_all_in_dict
from . import Component

_HIDDEN_ALIAS = u'???'
_HIDDEN_CLAN = u''

_METHOD_PATTERNS = re.compile(
    r'(member|legion|volunteer|slot|roster|player|unit|sortie|candidate)',
    re.IGNORECASE,
)


def _patch_player_info(pInfo, identity):
    if pInfo is None:
        return pInfo
    try:
        current_name = getattr(pInfo, 'name', None)
        if current_name != identity.original_name:
            return pInfo

        replacements = {'name': identity.new_name}
        if identity.new_clan and hasattr(pInfo, 'clanAbbrev'):
            replacements['clanAbbrev'] = identity.new_clan

        if hasattr(pInfo, '_replace'):
            try:
                return pInfo._replace(**replacements)
            except (ValueError, TypeError) as e:
                logger.debug("_replace failed: %s" % e)

        try:
            pInfo.name = identity.new_name
            if identity.new_clan and hasattr(pInfo, 'clanAbbrev'):
                pInfo.clanAbbrev = identity.new_clan
        except (AttributeError, TypeError) as e:
            logger.debug("setattr on pInfo failed: %s" % e)

    except Exception as e:
        logger.debug("_patch_player_info error: %s" % e)
    return pInfo


def _patch_player_info_hide_all(pInfo):
    """Replace any other player with ???."""
    if pInfo is None:
        return pInfo
    try:
        if getattr(pInfo, 'name', None):
            if hasattr(pInfo, '_replace'):
                try:
                    repl = {'name': _HIDDEN_ALIAS}
                    if hasattr(pInfo, 'clanAbbrev'):
                        repl['clanAbbrev'] = _HIDDEN_CLAN
                    return pInfo._replace(**repl)
                except (ValueError, TypeError):
                    pass
            try:
                pInfo.name = _HIDDEN_ALIAS
                if hasattr(pInfo, 'clanAbbrev'):
                    pInfo.clanAbbrev = _HIDDEN_CLAN
            except (AttributeError, TypeError):
                pass
    except Exception as e:
        logger.debug("_patch_player_info_hide_all error: %s" % e)
    return pInfo


class LobbyStrongholdComponent(Component):

    def __init__(self, controller):
        super(LobbyStrongholdComponent, self).__init__(controller)
        self._patched_converters = []
        self._vo_converters = None
        self._original_pinfo_new = None
        self._pinfo_class = None

    def setup_hooks(self):
        identity = self.identity

        UnitEntity = try_imports(
            lambda: __import__('gui.prb_control.entities.base.unit.entity', fromlist=['UnitEntity']).UnitEntity,
        )
        if UnitEntity is not None and hasattr(UnitEntity, '_buildPlayerInfo'):
            @override(UnitEntity, '_buildPlayerInfo')
            def hooked_build_player_info(baseMethod, baseObject, unitMgrID, unit, dbID, slotIdx=-1, data=None):
                if (settings.enabled
                        and identity.has_original
                        and data is not None
                        and data.get('name') == identity.original_name):
                    data = dict(data)
                    data['name'] = identity.new_name
                    if identity.new_clan:
                        data['clanAbbrev'] = identity.new_clan

                pInfo = baseMethod(baseObject, unitMgrID, unit, dbID, slotIdx=slotIdx, data=data)

                if settings.enabled and identity.has_original:
                    if getattr(pInfo, 'name', None) == identity.original_name:
                        pInfo = _patch_player_info(pInfo, identity)
                    elif settings.hide_all_nicknames and getattr(pInfo, 'name', None):
                        pInfo = _patch_player_info_hide_all(pInfo)
                    else:
                        pInfo = _patch_player_info(pInfo, identity)
                return pInfo

            if hasattr(UnitEntity, 'getCandidates'):
                @override(UnitEntity, 'getCandidates')
                def hooked_get_candidates(baseMethod, baseObject, unitMgrID=None):
                    result = baseMethod(baseObject, unitMgrID=unitMgrID)
                    if not settings.enabled or not identity.has_original or not result:
                        return result
                    patched = {}
                    hide_all = settings.hide_all_nicknames
                    for dbID, pInfo in result.items():
                        if getattr(pInfo, 'name', None) == identity.original_name:
                            patched[dbID] = _patch_player_info(pInfo, identity)
                        elif hide_all and getattr(pInfo, 'name', None):
                            patched[dbID] = _patch_player_info_hide_all(pInfo)
                        else:
                            patched[dbID] = _patch_player_info(pInfo, identity)
                    return patched

        try:
            import gui.Scaleform.daapi.view.lobby.fortifications.vo_converters as vo_converters
            self._vo_converters = vo_converters
            self._wrap_all_converters(vo_converters)
        except ImportError:
            logger.debug("vo_converters not available")
            self._vo_converters = None

        room_classes = []
        for path, name in (
            ('gui.Scaleform.daapi.view.lobby.fortifications.stronghold_battle_room', 'StrongholdBattleRoom'),
            ('gui.Scaleform.daapi.view.lobby.fortifications.fort_battle_room', 'FortBattleRoom'),
            ('gui.Scaleform.daapi.view.lobby.fortifications.fort_sortie_room', 'FortSortieRoom'),
            ('gui.Scaleform.daapi.view.lobby.strongholds.stronghold_battle_room', 'StrongholdBattleRoom'),
            ('gui.Scaleform.daapi.view.lobby.strongholds.stronghold_unit_view', 'StrongholdUnitView'),
            ('gui.impl.lobby.fortifications.stronghold_battle_room_view', 'StrongholdBattleRoomView'),
            ('gui.impl.lobby.fortifications.sortie_battle_room_view', 'SortieBattleRoomView'),
        ):
            cls = self._safe_import(path, name)
            if cls is not None:
                room_classes.append(cls)
                logger.debug("Room class found: %s.%s" % (path, name))

        for cls in room_classes:
            self._hook_room_methods(cls)

        try:
            from gui.prb_control.items import unit_items
            PlayerUnitInfo = getattr(unit_items, 'PlayerUnitInfo', None)
        except ImportError:
            PlayerUnitInfo = None

        if PlayerUnitInfo is not None and hasattr(PlayerUnitInfo, '__new__'):
            try:
                original_new = PlayerUnitInfo.__new__
                comp = self

                def patched_new(cls, *args, **kwargs):
                    instance = original_new(cls, *args, **kwargs)
                    if settings.enabled and identity.has_original:
                        try:
                            if getattr(instance, 'name', None) == identity.original_name:
                                if hasattr(instance, '_replace'):
                                    replace_kwargs = {'name': identity.new_name}
                                    if identity.new_clan and hasattr(instance, 'clanAbbrev'):
                                        replace_kwargs['clanAbbrev'] = identity.new_clan
                                    instance = instance._replace(**replace_kwargs)
                                else:
                                    instance.name = identity.new_name
                                    if identity.new_clan and hasattr(instance, 'clanAbbrev'):
                                        instance.clanAbbrev = identity.new_clan
                        except Exception as e:
                            logger.debug("PlayerUnitInfo __new__ patch error: %s" % e)
                    return instance

                self._original_pinfo_new = original_new
                self._pinfo_class = PlayerUnitInfo
                PlayerUnitInfo.__new__ = staticmethod(patched_new)
                logger.debug("PlayerUnitInfo.__new__ patched")
            except Exception as e:
                logger.debug("Failed to patch PlayerUnitInfo.__new__: %s" % e)

    def _safe_import(self, module_path, class_name):
        try:
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name, None)
        except (ImportError, AttributeError):
            return None
        except Exception as e:
            logger.debug("safe_import %s.%s failed: %s" % (module_path, class_name, e))
            return None

    def _hook_room_methods(self, cls):
        for attr_name in dir(cls):
            if attr_name.startswith('__'):
                continue
            if not (attr_name.startswith('_set') or attr_name.startswith('_update')
                    or attr_name.startswith('as_set')):
                continue
            if not _METHOD_PATTERNS.search(attr_name):
                continue
            method = getattr(cls, attr_name, None)
            if not callable(method):
                continue
            if getattr(method, '_nc_room_wrapped', False):
                continue
            try:
                self._wrap_room_method(cls, attr_name)
            except Exception as e:
                logger.debug("wrap %s.%s failed: %s" % (cls.__name__, attr_name, e))

    def _wrap_room_method(self, cls, attr_name):
        comp = self

        @override(cls, attr_name)
        def hooked(baseMethod, baseObject, *args, **kwargs):
            if settings.enabled and comp.identity.has_original:
                comp._deep_patch_args(args)
                comp._deep_patch_args(kwargs.values())
            return baseMethod(baseObject, *args, **kwargs)

        try:
            current = getattr(cls, attr_name)
            current._nc_room_wrapped = True
        except Exception:
            pass
        logger.debug("Hooked %s.%s" % (cls.__name__, attr_name))

    def _wrap_all_converters(self, vo_converters):
        identity = self.identity
        for attr_name in dir(vo_converters):
            if not attr_name.startswith('make'):
                continue
            target = getattr(vo_converters, attr_name, None)
            if not callable(target):
                continue
            if getattr(target, '_nc_wrapped', False):
                continue

            original = target

            def make_wrapper(orig, name):
                def wrapped(*args, **kwargs):
                    result = orig(*args, **kwargs)
                    if not settings.enabled or not identity.has_original:
                        return result
                    try:
                        self._deep_patch(result)
                    except Exception as e:
                        logger.debug("vo_converters.%s patch error: %s" % (name, e))
                    return result
                wrapped._nc_wrapped = True
                return wrapped

            wrapper = make_wrapper(original, attr_name)
            setattr(vo_converters, attr_name, wrapper)
            self._patched_converters.append((attr_name, original))
            logger.debug("vo_converters.%s wrapped" % attr_name)

    def _deep_patch(self, result):
        identity = self.identity
        if result is None:
            return
        if isinstance(result, tuple):
            for item in result:
                self._deep_patch(item)
            return
        if isinstance(result, (dict, list)):
            replace_all_in_dict(
                result, identity.original_name, identity.new_name,
                identity.new_clan if identity.new_clan else None)
            if settings.hide_all_nicknames:
                self._mask_others_in_dict(result, identity.original_name, identity.new_name)

    def _deep_patch_args(self, values):
        identity = self.identity
        for v in values:
            if isinstance(v, (dict, list)):
                try:
                    replace_all_in_dict(
                        v, identity.original_name, identity.new_name,
                        identity.new_clan if identity.new_clan else None)
                except Exception as e:
                    logger.debug("deep_patch_args error: %s" % e)
            elif isinstance(v, tuple):
                self._deep_patch_args(v)

    def _mask_others_in_dict(self, data, own_orig, own_new, _depth=0):
        if _depth > 10 or data is None:
            return
        _name_keys = ('name', 'userName', 'realName', 'fakeName', 'displayName', 'fullName')
        _clan_keys = ('clanAbbrev', 'clanTag')
        if isinstance(data, dict):
            for k in _name_keys:
                v = data.get(k)
                if v and v != own_orig and v != own_new:
                    data[k] = _HIDDEN_ALIAS
            for k in _clan_keys:
                v = data.get(k)
                if v and v != (self.identity.new_clan or ''):
                    data[k] = _HIDDEN_CLAN
            for v in data.values():
                if isinstance(v, (dict, list)):
                    self._mask_others_in_dict(v, own_orig, own_new, _depth + 1)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    self._mask_others_in_dict(item, own_orig, own_new, _depth + 1)

    def fini(self):
        if self._vo_converters and self._patched_converters:
            for name, original in self._patched_converters:
                try:
                    setattr(self._vo_converters, name, original)
                except Exception as e:
                    logger.debug("Failed to restore vo_converters.%s: %s" % (name, e))
            logger.debug("vo_converters restored: %d" % len(self._patched_converters))
        self._patched_converters = []
        self._vo_converters = None

        if self._pinfo_class is not None and self._original_pinfo_new is not None:
            try:
                self._pinfo_class.__new__ = staticmethod(self._original_pinfo_new)
                logger.debug("PlayerUnitInfo.__new__ restored")
            except Exception as e:
                logger.debug("Restore PlayerUnitInfo.__new__ failed: %s" % e)
        self._original_pinfo_new = None
        self._pinfo_class = None
