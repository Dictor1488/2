import BigWorld

from ..settings import settings
from ..utils import (
    logger, override, try_imports, make_weak_callback,
)
from ..platoon_tracker import platoon_tracker
from . import Component

_MAX_ARENA_RETRIES = 10
_RETRY_INTERVAL = 1.0
_DEFERRED_PATCH_DELAY = 0.5

_HIDDEN_ALIAS = u'???'
_HIDDEN_CLAN = u''
_BADGE_ATTR_MARKERS = ('badge', 'dogtag', 'insign', 'patch', 'emblem')


def _is_avatar_ready():
    try:
        player = BigWorld.player()
        if player is None:
            return False
        if not hasattr(player, 'arena'):
            return False
        if not hasattr(player, 'inputHandler') or player.inputHandler is None:
            return False
        return True
    except Exception:
        return False


def _is_world_valid():
    try:
        player = BigWorld.player()
        if player is None:
            return False
        if hasattr(player, 'spaceID'):
            return player.spaceID != 0
        return True
    except Exception:
        return False


def _clear_badge_value(container, key, value):
    try:
        if isinstance(value, list):
            setattr(container, key, [])
        elif isinstance(value, dict):
            setattr(container, key, {})
        elif isinstance(value, tuple):
            setattr(container, key, ())
        elif isinstance(value, bool):
            setattr(container, key, False)
        elif isinstance(value, (int, long)):
            setattr(container, key, 0)
        else:
            setattr(container, key, None)
    except Exception:
        pass


def _strip_badges_obj(obj):
    try:
        if obj is None:
            return
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                low = key.lower()
                if any(marker in low for marker in _BADGE_ATTR_MARKERS):
                    value = obj.get(key)
                    if isinstance(value, list):
                        obj[key] = []
                    elif isinstance(value, dict):
                        obj[key] = {}
                    elif isinstance(value, tuple):
                        obj[key] = ()
                    elif isinstance(value, bool):
                        obj[key] = False
                    elif isinstance(value, (int, long)):
                        obj[key] = 0
                    else:
                        obj[key] = None
            return

        for attr in dir(obj):
            if attr.startswith('_'):
                continue
            low = attr.lower()
            if not any(marker in low for marker in _BADGE_ATTR_MARKERS):
                continue
            try:
                value = getattr(obj, attr)
            except Exception:
                continue
            _clear_badge_value(obj, attr, value)
    except Exception as e:
        logger.debug('_strip_badges_obj error: %s' % e)


def _patch_veh_info_obj(veh_info, identity):
    from ..settings import settings as _settings
    try:
        _strip_badges_obj(veh_info)
        if not hasattr(veh_info, 'name'):
            return veh_info
        veh_name = veh_info.name
        if veh_name != identity.original_name:
            if platoon_tracker.is_platoon_mate(veh_name):
                alias = platoon_tracker.get_alias(veh_name)
                try:
                    veh_info.name = alias
                    if hasattr(veh_info, 'clanAbbrev'):
                        veh_info.clanAbbrev = _HIDDEN_CLAN
                    if hasattr(veh_info, 'fakeName') and veh_info.fakeName == veh_name:
                        veh_info.fakeName = alias
                    _strip_badges_obj(veh_info)
                except (AttributeError, TypeError):
                    if hasattr(veh_info, '_replace'):
                        repl = {'name': alias}
                        if hasattr(veh_info, 'fakeName') and veh_info.fakeName == veh_name:
                            repl['fakeName'] = alias
                        try:
                            return veh_info._replace(**repl)
                        except (ValueError, TypeError):
                            pass
            elif _settings.hide_all_nicknames and veh_name:
                try:
                    veh_info.name = _HIDDEN_ALIAS
                    if hasattr(veh_info, 'clanAbbrev'):
                        veh_info.clanAbbrev = _HIDDEN_CLAN
                    if hasattr(veh_info, 'fakeName') and veh_info.fakeName == veh_name:
                        veh_info.fakeName = _HIDDEN_ALIAS
                    _strip_badges_obj(veh_info)
                except (AttributeError, TypeError):
                    if hasattr(veh_info, '_replace'):
                        repl = {'name': _HIDDEN_ALIAS}
                        if hasattr(veh_info, 'fakeName') and veh_info.fakeName == veh_name:
                            repl['fakeName'] = _HIDDEN_ALIAS
                        try:
                            return veh_info._replace(**repl)
                        except (ValueError, TypeError):
                            pass
            return veh_info
        if veh_info.name != identity.original_name:
            return veh_info
        try:
            veh_info.name = identity.new_name
            if hasattr(veh_info, 'fakeName') and veh_info.fakeName == identity.original_name:
                veh_info.fakeName = identity.new_name
            if identity.new_clan and hasattr(veh_info, 'clanAbbrev'):
                veh_info.clanAbbrev = identity.new_clan
            _strip_badges_obj(veh_info)
            return veh_info
        except (AttributeError, TypeError):
            pass
        if hasattr(veh_info, '_replace'):
            replacements = {'name': identity.new_name}
            if hasattr(veh_info, 'fakeName') and veh_info.fakeName == identity.original_name:
                replacements['fakeName'] = identity.new_name
            if identity.new_clan and hasattr(veh_info, 'clanAbbrev'):
                replacements['clanAbbrev'] = identity.new_clan
            try:
                return veh_info._replace(**replacements)
            except (ValueError, TypeError):
                pass
    except Exception as e:
        logger.debug('_patch_veh_info_obj error: %s' % e)
    return veh_info


def _patch_veh_info_list(veh_info_list, identity):
    if not veh_info_list:
        return veh_info_list
    try:
        result = []
        changed = False
        for item in veh_info_list:
            patched = _patch_veh_info_obj(item, identity)
            if patched is not item:
                changed = True
            result.append(patched)
        if changed:
            if isinstance(veh_info_list, tuple):
                return tuple(result)
            return result
        return veh_info_list
    except Exception as e:
        logger.debug('_patch_veh_info_list error: %s' % e)
        return veh_info_list


class BattleArenaComponent(Component):

    def __init__(self, controller):
        super(BattleArenaComponent, self).__init__(controller)
        self._arena_retries = 0
        self._retry_active = False
        self._current_battle_id = None
        self._patched_this_battle = False
        self._callback_generation = 0
        self._patched_arenas = set()

    def setup_hooks(self):
        identity = self.identity
        comp = self

        try:
            from ClientArena import ClientArena
            from constants import ARENA_UPDATE
        except ImportError:
            logger.debug('ClientArena not available')
            ClientArena = None
            ARENA_UPDATE = None

        if ClientArena is not None:
            if hasattr(ClientArena, 'updateVehiclesList'):
                @override(ClientArena, 'updateVehiclesList')
                def hooked_update_vehicles_list(baseMethod, baseObject, vehInfoList):
                    if settings.enabled and identity.has_original:
                        try:
                            vehInfoList = _patch_veh_info_list(vehInfoList, identity)
                        except Exception as e:
                            logger.debug('updateVehiclesList patch error: %s' % e)
                    return baseMethod(baseObject, vehInfoList)

            if hasattr(ClientArena, 'update') and ARENA_UPDATE is not None:
                @override(ClientArena, 'update')
                def hooked_arena_update(baseMethod, baseObject, updateType, argStr):
                    if (settings.enabled and identity.has_original
                            and updateType == ARENA_UPDATE.VEHICLE_LIST):
                        try:
                            import cPickle
                            import zlib
                            info_tuple = cPickle.loads(zlib.decompress(argStr))
                            patched = _patch_veh_info_list(info_tuple, identity)
                            argStr = zlib.compress(cPickle.dumps(patched), 1)
                        except Exception as e:
                            logger.debug('arena.update VEHICLE_LIST patch error: %s' % e)
                    return baseMethod(baseObject, updateType, argStr)

        BattlePage = try_imports(
            lambda: __import__('gui.Scaleform.daapi.view.battle.classic.page', fromlist=['ClassicPage']).ClassicPage,
            lambda: __import__('gui.Scaleform.daapi.view.battle.shared.page', fromlist=['SharedPage']).SharedPage,
        )
        if BattlePage and hasattr(BattlePage, '_populate'):
            @override(BattlePage, '_populate')
            def hooked_populate(baseMethod, baseObject, *args, **kwargs):
                result = baseMethod(baseObject, *args, **kwargs)
                if settings.enabled and identity.has_original and _is_avatar_ready():
                    gen = comp._callback_generation
                    BigWorld.callback(_DEFERRED_PATCH_DELAY,
                                      make_weak_callback(comp, '_safe_deferred_patch', gen))
                return result

        try:
            from gui.battle_control.arena_info.arena_dp import ArenaDataProvider
        except ImportError:
            ArenaDataProvider = None
        if ArenaDataProvider:
            method = 'buildVehiclesData' if hasattr(ArenaDataProvider, 'buildVehiclesData') else (
                'updateVehiclesInfo' if hasattr(ArenaDataProvider, 'updateVehiclesInfo') else None)
            if method:
                @override(ArenaDataProvider, method)
                def hooked_arena_dp(baseMethod, baseObject, *args, **kwargs):
                    result = baseMethod(baseObject, *args, **kwargs)
                    if settings.enabled and identity.has_original and _is_avatar_ready():
                        gen = comp._callback_generation
                        BigWorld.callback(_DEFERRED_PATCH_DELAY,
                                          make_weak_callback(comp, '_safe_deferred_patch', gen))
                    return result

        try:
            from gui.battle_control.arena_info.arena_vos import VehicleArenaInfoVO
        except ImportError:
            VehicleArenaInfoVO = None
        if VehicleArenaInfoVO and hasattr(VehicleArenaInfoVO, 'update'):
            @override(VehicleArenaInfoVO, 'update')
            def hooked_vo_update(baseMethod, baseObject, *args, **kwargs):
                result = baseMethod(baseObject, *args, **kwargs)
                if not settings.enabled or not identity.has_original:
                    return result
                if hasattr(baseObject, 'player') and baseObject.player:
                    pvo = baseObject.player
                    try:
                        _strip_badges_obj(pvo)
                        if hasattr(pvo, 'name') and pvo.name == identity.original_name:
                            try:
                                pvo.name = identity.new_name
                                if identity.new_clan and hasattr(pvo, 'clanAbbrev'):
                                    pvo.clanAbbrev = identity.new_clan
                                if hasattr(pvo, 'fakeName') and pvo.fakeName == identity.original_name:
                                    pvo.fakeName = identity.new_name
                                _strip_badges_obj(pvo)
                            except (AttributeError, TypeError):
                                pass
                    except Exception:
                        pass
                return result

    def on_avatar_ready(self):
        if not settings.enabled or not self.identity.has_original:
            return
        try:
            player = BigWorld.player()
            if player is None or not hasattr(player, 'arena') or not _is_world_valid():
                return
            self._patch_arena_vehicles_if_ready()
            self._start_replace(self._callback_generation)
        except Exception as e:
            logger.error('battle on_avatar_ready: %s' % e)

    def on_avatar_become_non_player(self):
        self._callback_generation += 1
        self._reset()
        self._patched_arenas.clear()

    def on_settings_changed(self):
        try:
            player = BigWorld.player()
            if player is None or not hasattr(player, 'arena') or not _is_world_valid():
                return
            self._patched_arenas.clear()
            self._patched_this_battle = False
            if settings.enabled and self.identity.has_original:
                self._patch_arena_vehicles_if_ready()
                self._patch_arena_dp()
                self._patched_this_battle = True
        except Exception as e:
            logger.debug('battle on_settings_changed: %s' % e)

    def _reset(self):
        self._retry_active = False
        self._arena_retries = 0
        self._current_battle_id = None
        self._patched_this_battle = False

    def _get_battle_id(self):
        try:
            player = BigWorld.player()
            if player and hasattr(player, 'arenaUniqueID'):
                return player.arenaUniqueID
        except Exception:
            pass
        return None

    def _start_replace(self, generation):
        battle_id = self._get_battle_id()
        if self._patched_this_battle and self._current_battle_id == battle_id:
            return
        if self._retry_active and self._current_battle_id == battle_id:
            return
        self._retry_active = True
        self._current_battle_id = battle_id
        self._arena_retries = 0
        self._try_replace(generation)

    def _try_replace(self, generation):
        if generation != self._callback_generation:
            self._retry_active = False
            return
        try:
            if not _is_world_valid():
                self._retry_active = False
                return
            player = BigWorld.player()
            if not player or not hasattr(player, 'arena') or not player.arena:
                self._retry_or_abort(generation)
                return
            arena = player.arena
            has_vehicles = hasattr(arena, 'vehicles') and arena.vehicles
            has_player_vehicle = hasattr(player, 'playerVehicleID') and player.playerVehicleID
            if not has_vehicles or not has_player_vehicle:
                self._retry_or_abort(generation)
                return
            self._arena_retries = 0
            self._retry_active = False
            self._patched_this_battle = True
            self._patch_arena_vehicles(arena)
            self._patch_arena_dp()
        except Exception as e:
            logger.error('_try_replace error: %s' % e)
            self._retry_active = False

    def _retry_or_abort(self, generation):
        self._arena_retries += 1
        if self._arena_retries < _MAX_ARENA_RETRIES:
            BigWorld.callback(_RETRY_INTERVAL, make_weak_callback(self, '_try_replace', generation))
        else:
            self._retry_active = False

    def _patch_arena_vehicles_if_ready(self):
        try:
            player = BigWorld.player()
            if player and hasattr(player, 'arena') and player.arena:
                self._patch_arena_vehicles(player.arena)
        except Exception as e:
            logger.debug('early arena patch failed: %s' % e)

    def _patch_arena_vehicles(self, arena):
        try:
            if not settings.enabled or not hasattr(arena, 'vehicles'):
                return
            arena_id = id(arena)
            if arena_id in self._patched_arenas:
                return
            identity = self.identity
            hide_all = settings.hide_all_nicknames
            for vehicleID, vehicleData in arena.vehicles.items():
                if not isinstance(vehicleData, dict):
                    continue
                _strip_badges_obj(vehicleData)
                veh_name = vehicleData.get('name', '')
                if veh_name == identity.original_name:
                    vehicleData['name'] = identity.new_name
                    if identity.new_clan:
                        vehicleData['clanAbbrev'] = identity.new_clan
                    if vehicleData.get('fakeName') == identity.original_name:
                        vehicleData['fakeName'] = identity.new_name
                elif platoon_tracker.is_platoon_mate(veh_name):
                    alias = platoon_tracker.get_alias(veh_name)
                    vehicleData['name'] = alias
                    vehicleData['clanAbbrev'] = _HIDDEN_CLAN
                    if vehicleData.get('fakeName') == veh_name:
                        vehicleData['fakeName'] = alias
                elif hide_all and veh_name:
                    vehicleData['name'] = _HIDDEN_ALIAS
                    vehicleData['clanAbbrev'] = _HIDDEN_CLAN
                    if vehicleData.get('fakeName') == veh_name:
                        vehicleData['fakeName'] = _HIDDEN_ALIAS
                _strip_badges_obj(vehicleData)
            self._patched_arenas.add(arena_id)
        except Exception as e:
            logger.error('arena vehicles patch error: %s' % e)

    def _patch_arena_dp(self):
        try:
            if not settings.enabled:
                return
            session_provider = self.controller.session_provider
            if not session_provider:
                return
            arenaDP = None
            if hasattr(session_provider, 'getArenaDP'):
                arenaDP = session_provider.getArenaDP()
            elif hasattr(session_provider, 'arenaDP'):
                arenaDP = session_provider.arenaDP
            if arenaDP is None:
                return
            identity = self.identity
            if hasattr(arenaDP, 'getVehiclesInfoIterator'):
                for vInfoVO in arenaDP.getVehiclesInfoIterator():
                    if not hasattr(vInfoVO, 'player') or not vInfoVO.player:
                        continue
                    pvo = vInfoVO.player
                    try:
                        _strip_badges_obj(pvo)
                        pvo_name = getattr(pvo, 'name', None)
                        if pvo_name == identity.original_name:
                            try:
                                pvo.name = identity.new_name
                                if identity.new_clan and hasattr(pvo, 'clanAbbrev'):
                                    pvo.clanAbbrev = identity.new_clan
                                if hasattr(pvo, 'fakeName') and pvo.fakeName == identity.original_name:
                                    pvo.fakeName = identity.new_name
                            except (AttributeError, TypeError):
                                pass
                        elif pvo_name and platoon_tracker.is_platoon_mate(pvo_name):
                            alias = platoon_tracker.get_alias(pvo_name)
                            try:
                                pvo.name = alias
                                if hasattr(pvo, 'clanAbbrev'):
                                    pvo.clanAbbrev = _HIDDEN_CLAN
                                if hasattr(pvo, 'fakeName') and pvo.fakeName == pvo_name:
                                    pvo.fakeName = alias
                            except (AttributeError, TypeError):
                                pass
                        elif pvo_name and settings.hide_all_nicknames and pvo_name != identity.original_name:
                            try:
                                pvo.name = _HIDDEN_ALIAS
                                if hasattr(pvo, 'clanAbbrev'):
                                    pvo.clanAbbrev = _HIDDEN_CLAN
                                if hasattr(pvo, 'fakeName') and pvo.fakeName == pvo_name:
                                    pvo.fakeName = _HIDDEN_ALIAS
                            except (AttributeError, TypeError):
                                pass
                        _strip_badges_obj(pvo)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug('arenaDP patch error: %s' % e)

    def _safe_deferred_patch(self, generation):
        if generation != self._callback_generation:
            return
        if not _is_avatar_ready() or not _is_world_valid():
            return
        try:
            player = BigWorld.player()
            if player and hasattr(player, 'arena') and player.arena:
                self._patch_arena_vehicles(player.arena)
            self._patch_arena_dp()
            self._patched_this_battle = True
            self._current_battle_id = self._get_battle_id()
        except Exception as e:
            logger.debug('deferred patch error: %s' % e)
