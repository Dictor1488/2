import BigWorld

from ..settings import settings
from ..utils import (
    logger, override, try_imports, make_weak_callback,
)
from ..platoon_tracker import platoon_tracker
from . import Component

import re as _re

_MAX_ARENA_RETRIES = 10
_SERVER_SUFFIX_RE = _re.compile(r'#\d+$')


def _strip_server_suffix(name):
    """Remove trailing server/cluster number like '#1234' from a player name."""
    if name and isinstance(name, str):
        return _SERVER_SUFFIX_RE.sub('', name)
    try:
        # Python 2 unicode
        if name and isinstance(name, unicode):
            return _SERVER_SUFFIX_RE.sub(u'', name)
    except NameError:
        pass
    return name
_RETRY_INTERVAL = 1.0
_DEFERRED_PATCH_DELAY = 0.5

_HIDDEN_CLAN = u''


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


class BattleArenaComponent(Component):

    def __init__(self, controller):
        super(BattleArenaComponent, self).__init__(controller)
        self._arena_retries = 0
        self._retry_active = False
        self._current_battle_id = None
        self._patched_this_battle = False
        self._callback_generation = 0
        self._patched_arenas = set()
        self._aliases = {}
        self._next_alias = 1

    def _reset_aliases(self):
        self._aliases = {}
        self._next_alias = 1

    def _get_hidden_alias(self, key):
        alias = self._aliases.get(key)
        if alias is None:
            alias = u'Player %d' % self._next_alias
            self._aliases[key] = alias
            self._next_alias += 1
        return alias

    def _is_own_vehicle(self, vehicleID, vehicleData):
        try:
            player = BigWorld.player()
            if player is not None and hasattr(player, 'playerVehicleID'):
                if player.playerVehicleID and vehicleID == player.playerVehicleID:
                    return True
        except Exception:
            pass

        if isinstance(vehicleData, dict):
            if vehicleData.get('isCurrentPlayer') is True:
                return True
            veh_name = vehicleData.get('name', '')
            fake_name = vehicleData.get('fakeName', '')
            if veh_name in (self.identity.original_name, self.identity.new_name):
                return True
            if fake_name in (self.identity.original_name, self.identity.new_name):
                return True
        return False

    def _apply_own_to_dict(self, vehicleData):
        display_name = self.identity.new_name
        if settings.hide_server:
            display_name = _strip_server_suffix(display_name)
        vehicleData['name'] = display_name
        if vehicleData.get('fakeName') == self.identity.original_name:
            vehicleData['fakeName'] = display_name
        if self.identity.new_clan is not None:
            vehicleData['clanAbbrev'] = self.identity.new_clan

    def _apply_other_to_dict(self, vehicleData, alias, original_name):
        vehicleData['name'] = alias
        vehicleData['clanAbbrev'] = _HIDDEN_CLAN
        if vehicleData.get('fakeName') == original_name:
            vehicleData['fakeName'] = alias

    def _patch_veh_info_obj(self, veh_info):
        try:
            if not hasattr(veh_info, 'name'):
                return veh_info

            veh_name = veh_info.name
            if not veh_name:
                return veh_info

            if veh_name == self.identity.original_name:
                _own_display = self.identity.new_name
                if settings.hide_server:
                    _own_display = _strip_server_suffix(_own_display)
                try:
                    veh_info.name = _own_display
                    if hasattr(veh_info, 'fakeName') and veh_info.fakeName == self.identity.original_name:
                        veh_info.fakeName = _own_display
                    if self.identity.new_clan is not None and hasattr(veh_info, 'clanAbbrev'):
                        veh_info.clanAbbrev = self.identity.new_clan
                    return veh_info
                except (AttributeError, TypeError):
                    pass

                if hasattr(veh_info, '_replace'):
                    replacements = {'name': _own_display}
                    if hasattr(veh_info, 'fakeName') and veh_info.fakeName == self.identity.original_name:
                        replacements['fakeName'] = _own_display
                    if self.identity.new_clan is not None and hasattr(veh_info, 'clanAbbrev'):
                        replacements['clanAbbrev'] = self.identity.new_clan
                    try:
                        return veh_info._replace(**replacements)
                    except (ValueError, TypeError):
                        return veh_info
                return veh_info

            if platoon_tracker.is_platoon_mate(veh_name):
                alias = platoon_tracker.get_alias(veh_name)
            elif settings.hide_all_nicknames:
                alias = self._get_hidden_alias(veh_name)
            else:
                return veh_info

            try:
                veh_info.name = alias
                if hasattr(veh_info, 'clanAbbrev'):
                    veh_info.clanAbbrev = _HIDDEN_CLAN
                if hasattr(veh_info, 'fakeName') and veh_info.fakeName == veh_name:
                    veh_info.fakeName = alias
                return veh_info
            except (AttributeError, TypeError):
                pass

            if hasattr(veh_info, '_replace'):
                replacements = {'name': alias}
                if hasattr(veh_info, 'fakeName') and veh_info.fakeName == veh_name:
                    replacements['fakeName'] = alias
                if hasattr(veh_info, 'clanAbbrev'):
                    replacements['clanAbbrev'] = _HIDDEN_CLAN
                try:
                    return veh_info._replace(**replacements)
                except (ValueError, TypeError):
                    return veh_info
        except Exception as e:
            logger.debug("_patch_veh_info_obj error: %s" % e)
        return veh_info

    def _patch_veh_info_list(self, veh_info_list):
        if not veh_info_list:
            return veh_info_list
        try:
            result = []
            changed = False
            for item in veh_info_list:
                patched = self._patch_veh_info_obj(item)
                if patched is not item:
                    changed = True
                result.append(patched)
            if changed:
                if isinstance(veh_info_list, tuple):
                    return tuple(result)
                return result
            return veh_info_list
        except Exception as e:
            logger.debug("_patch_veh_info_list error: %s" % e)
            return veh_info_list

    def setup_hooks(self):
        identity = self.identity
        comp = self

        try:
            from ClientArena import ClientArena
            from constants import ARENA_UPDATE
        except ImportError:
            logger.debug("ClientArena not available")
            ClientArena = None
            ARENA_UPDATE = None

        if ClientArena is not None:
            if hasattr(ClientArena, 'updateVehiclesList'):
                @override(ClientArena, 'updateVehiclesList')
                def hooked_update_vehicles_list(baseMethod, baseObject, vehInfoList):
                    if settings.enabled and identity.has_original:
                        try:
                            vehInfoList = comp._patch_veh_info_list(vehInfoList)
                        except Exception as e:
                            logger.debug("updateVehiclesList patch error: %s" % e)
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
                            patched = comp._patch_veh_info_list(info_tuple)
                            argStr = zlib.compress(cPickle.dumps(patched), 1)
                        except Exception as e:
                            logger.debug("arena.update VEHICLE_LIST patch error: %s" % e)
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
                        if hasattr(pvo, 'name') and pvo.name == identity.original_name:
                            try:
                                pvo.name = identity.new_name
                                if identity.new_clan is not None and hasattr(pvo, 'clanAbbrev'):
                                    pvo.clanAbbrev = identity.new_clan
                                if hasattr(pvo, 'fakeName') and pvo.fakeName == identity.original_name:
                                    pvo.fakeName = identity.new_name
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
            self._reset_aliases()
            self._patch_arena_vehicles_if_ready()
            self._start_replace(self._callback_generation)
        except Exception as e:
            logger.error("battle on_avatar_ready: %s" % e)

    def on_avatar_become_non_player(self):
        self._callback_generation += 1
        self._reset()
        self._patched_arenas.clear()
        self._reset_aliases()

    def on_settings_changed(self):
        try:
            player = BigWorld.player()
            if player is None or not hasattr(player, 'arena') or not _is_world_valid():
                return
            self._patched_arenas.clear()
            self._patched_this_battle = False
            self._reset_aliases()
            if settings.enabled and self.identity.has_original:
                self._patch_arena_vehicles_if_ready()
                self._patch_arena_dp()
                self._patched_this_battle = True
        except Exception as e:
            logger.debug("battle on_settings_changed: %s" % e)

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
            logger.error("_try_replace error: %s" % e)
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
            logger.debug("early arena patch failed: %s" % e)

    def _patch_arena_vehicles(self, arena):
        try:
            if not settings.enabled or not hasattr(arena, 'vehicles'):
                return
            arena_id = id(arena)
            if arena_id in self._patched_arenas:
                return

            hide_all = settings.hide_all_nicknames
            for vehicleID, vehicleData in arena.vehicles.items():
                if not isinstance(vehicleData, dict):
                    continue

                veh_name = vehicleData.get('name', '')
                if self._is_own_vehicle(vehicleID, vehicleData):
                    self._apply_own_to_dict(vehicleData)
                elif veh_name and platoon_tracker.is_platoon_mate(veh_name):
                    alias = platoon_tracker.get_alias(veh_name)
                    self._apply_other_to_dict(vehicleData, alias, veh_name)
                elif hide_all and veh_name:
                    alias = self._get_hidden_alias(veh_name)
                    self._apply_other_to_dict(vehicleData, alias, veh_name)

            self._patched_arenas.add(arena_id)
        except Exception as e:
            logger.error("arena vehicles patch error: %s" % e)

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

            player_vehicle_id = None
            try:
                player = BigWorld.player()
                if player and hasattr(player, 'playerVehicleID'):
                    player_vehicle_id = player.playerVehicleID
            except Exception:
                pass

            if hasattr(arenaDP, 'getVehiclesInfoIterator'):
                for vInfoVO in arenaDP.getVehiclesInfoIterator():
                    if not hasattr(vInfoVO, 'player') or not vInfoVO.player:
                        continue
                    pvo = vInfoVO.player
                    try:
                        pvo_name = getattr(pvo, 'name', None)
                        v_id = getattr(vInfoVO, 'vehicleID', None)
                        if player_vehicle_id is not None and v_id == player_vehicle_id:
                            try:
                                pvo.name = self.identity.new_name
                                if hasattr(pvo, 'fakeName') and pvo.fakeName == self.identity.original_name:
                                    pvo.fakeName = self.identity.new_name
                                if self.identity.new_clan is not None and hasattr(pvo, 'clanAbbrev'):
                                    pvo.clanAbbrev = self.identity.new_clan
                            except (AttributeError, TypeError):
                                pass
                        elif pvo_name == self.identity.original_name:
                            try:
                                pvo.name = self.identity.new_name
                                if hasattr(pvo, 'fakeName') and pvo.fakeName == self.identity.original_name:
                                    pvo.fakeName = self.identity.new_name
                                if self.identity.new_clan is not None and hasattr(pvo, 'clanAbbrev'):
                                    pvo.clanAbbrev = self.identity.new_clan
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
                        elif pvo_name and settings.hide_all_nicknames:
                            alias = self._get_hidden_alias(pvo_name)
                            try:
                                pvo.name = alias
                                if hasattr(pvo, 'clanAbbrev'):
                                    pvo.clanAbbrev = _HIDDEN_CLAN
                                if hasattr(pvo, 'fakeName') and pvo.fakeName == pvo_name:
                                    pvo.fakeName = alias
                            except (AttributeError, TypeError):
                                pass
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("arenaDP patch error: %s" % e)

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
            logger.debug("deferred patch error: %s" % e)
