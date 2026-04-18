from .utils import logger, replace_all_in_dict, format_full_name
from .platoon_tracker import platoon_tracker

_HIDDEN_ALIAS = u"???"
_HIDDEN_CLAN = u""
_NAME_KEYS = frozenset(("userName", "displayName", "fullName"))
_DISPLAY_NAME_KEYS = frozenset(("userName", "displayName", "fullName"))

_PLAYER_INFO_ATTRS = ('name', 'userName', 'displayName', 'fullName', 'realName', 'fakeName')
_CLAN_ATTRS = ('clanAbbrev', 'clanTag')
_PRIVATE_NAME_ATTRS = ('_PlayerInfo__realName', '_PlayerInfo__fakeName')
_PRIVATE_CLAN_ATTRS = ('_PlayerInfo__clanAbbrev',)

_RESULTS_PATCHED_MARKER = '_nc_results_patched'

_HIDDEN_ALIAS = u'???'
_HIDDEN_CLAN = u''


def _orig(identity):
    return identity.original_name


def _nick(identity):
    return identity.new_name


def _clan(identity):
    return identity.new_clan


def _is_hide_all():
    from .settings import settings
    return settings.enabled and settings.hide_all_nicknames


def patch_vo_dict(playerVO, identity):
    """Patch a player VO dict in place. Used by lobby PRB entities."""
    if not playerVO or not identity.has_original:
        return playerVO
    uname = playerVO.get('userName', '')
    if uname == _orig(identity):
        playerVO['userName'] = _nick(identity)
        if _clan(identity):
            playerVO['clanAbbrev'] = _clan(identity)
        playerVO['fullName'] = format_full_name(
            _nick(identity),
            _clan(identity) or playerVO.get('clanAbbrev', ''))
        logger.debug("Patched playerVO userName")
    elif _clan(identity) and uname == _nick(identity):
        playerVO['clanAbbrev'] = _clan(identity)
        playerVO['fullName'] = format_full_name(_nick(identity), _clan(identity))
    elif uname and platoon_tracker.is_platoon_mate(uname):
        alias = platoon_tracker.get_alias(uname)
        playerVO['userName'] = alias
        playerVO['clanAbbrev'] = _HIDDEN_CLAN
        playerVO['fullName'] = alias
        logger.debug("Patched platoon mate playerVO: %s -> %s" % (uname, alias))
    elif uname and _is_hide_all() and uname != _orig(identity):
        playerVO['userName'] = _HIDDEN_ALIAS
        playerVO['clanAbbrev'] = _HIDDEN_CLAN
        playerVO['fullName'] = _HIDDEN_ALIAS
        logger.debug("hide_all: masked playerVO userName %s" % uname)
    return playerVO


def patch_raw_results(result, identity):
    """Deep-patch a battle results dict. Marks the dict to avoid repeat work."""
    if not result or not identity.has_original:
        return
    if isinstance(result, dict):
        if result.get(_RESULTS_PATCHED_MARKER):
            return
    patch_battle_results_avatars(result, identity)
    replace_all_in_dict(
        result, _orig(identity), _nick(identity),
        _clan(identity) if _clan(identity) else None)
    from .settings import settings as _settings
    if _settings.hide_all_nicknames:
        mask_all_nicknames_in_results(result, identity)
    if isinstance(result, dict):
        result[_RESULTS_PATCHED_MARKER] = True


def patch_personal_info_data(personal_info, identity):
    try:
        if not hasattr(personal_info, 'avatar') or not hasattr(personal_info.avatar, 'name'):
            return
        if personal_info.avatar.name == _orig(identity):
            personal_info.avatar.name = _nick(identity)
            logger.debug("Patched personal_info.avatar.name")
            if _clan(identity) and hasattr(personal_info.avatar, 'clanAbbrev'):
                personal_info.avatar.clanAbbrev = _clan(identity)
    except Exception as e:
        logger.error("personal_info patch error: %s" % e)


def patch_reusable_info_deep(reusableInfo, identity):
    try:
        if hasattr(reusableInfo, 'personal') and reusableInfo.personal:
            if hasattr(reusableInfo.personal, 'avatar'):
                _patch_avatar_attrs(reusableInfo.personal.avatar, identity, "personal.avatar")
        if hasattr(reusableInfo, 'common') and hasattr(reusableInfo.common, 'avatars'):
            for avatar_id, avatarInfo in reusableInfo.common.avatars.items():
                _patch_avatar_attrs(avatarInfo, identity, "common.avatar[%s]" % avatar_id)
    except Exception as e:
        logger.error("reusable_info deep patch error: %s" % e)


def _patch_avatar_attrs(avatar, identity, label):
    patched_name = False
    for attr in _PLAYER_INFO_ATTRS:
        if hasattr(avatar, attr) and getattr(avatar, attr) == _orig(identity):
            setattr(avatar, attr, _nick(identity))
            patched_name = True
    if patched_name and _clan(identity):
        for clan_attr in _CLAN_ATTRS:
            if hasattr(avatar, clan_attr):
                setattr(avatar, clan_attr, _clan(identity))
    if patched_name:
        logger.debug("Patched %s" % label)
        return

    # Do not mask avatar internals in hide_all mode. Battle Results UI uses
    # these objects to distinguish players, and replacing all names with the
    # same alias breaks selecting a specific player in the results screen.


def patch_reusable_info_players(reusableInfo, identity):
    try:
        if not hasattr(reusableInfo, 'players'):
            return
        players = reusableInfo.players
        if hasattr(players, 'getPlayerInfoIterator'):
            for dbID, playerInfo in players.getPlayerInfoIterator():
                _patch_player_info(playerInfo, identity, dbID)
        elif hasattr(players, 'items'):
            for dbID, playerInfo in players.items():
                _patch_player_info(playerInfo, identity, dbID)
    except Exception as e:
        logger.error("reusable_info players patch error: %s" % e)


def _patch_player_info(playerInfo, identity, dbID):
    try:
        patched = False
        for attr in _PLAYER_INFO_ATTRS:
            if hasattr(playerInfo, attr) and getattr(playerInfo, attr) == _orig(identity):
                setattr(playerInfo, attr, _nick(identity))
                patched = True

        if not patched:
            for attr in _PRIVATE_NAME_ATTRS:
                if hasattr(playerInfo, attr) and getattr(playerInfo, attr) == _orig(identity):
                    setattr(playerInfo, attr, _nick(identity))
                    patched = True

        if patched and _clan(identity):
            for attr in _CLAN_ATTRS + _PRIVATE_CLAN_ATTRS:
                if hasattr(playerInfo, attr):
                    setattr(playerInfo, attr, _clan(identity))
            logger.debug("Patched PlayerInfo for dbID=%s" % dbID)
            return

        # Do not mask PlayerInfo internals in hide_all mode. The battle
        # results screen relies on these values to keep players distinct.
    except Exception as e:
        logger.error("PlayerInfo patch error for dbID=%s: %s" % (dbID, e))


def patch_battle_results_avatars(data, identity):
    try:
        if not isinstance(data, dict):
            return
        if 'avatars' in data and isinstance(data['avatars'], dict):
            for avatar_id, avatar_data in data['avatars'].items():
                if not isinstance(avatar_data, dict):
                    continue
                name_patched = False
                for key in ('name', 'userName', 'realName', 'fakeName', 'displayName'):
                    if key in avatar_data and avatar_data[key] == _orig(identity):
                        avatar_data[key] = _nick(identity)
                        name_patched = True
                if name_patched and _clan(identity):
                    for ck in _CLAN_ATTRS:
                        if ck in avatar_data:
                            avatar_data[ck] = _clan(identity)

        for key in ('players', 'vehicles', 'personal', 'common'):
            if key in data and isinstance(data[key], (dict, list)):
                replace_all_in_dict(
                    data[key], _orig(identity), _nick(identity),
                    _clan(identity) if _clan(identity) else None)
    except Exception as e:
        logger.error("battle_results avatars patch error: %s" % e)


def patch_battle_results_view(view_instance, identity):
    try:
        if hasattr(view_instance, '_reusableInfo') and view_instance._reusableInfo:
            patch_reusable_info_players(view_instance._reusableInfo, identity)
        if hasattr(view_instance, '_personalInfo') and view_instance._personalInfo:
            patch_personal_info_data(view_instance._personalInfo, identity)
    except Exception as e:
        logger.error("battle_results view patch error: %s" % e)


def mask_all_nicknames_in_results(data, identity):
    """When hide_all_nicknames is on, replace every player name that is NOT
    the own player with '???'. Must be called after own-name patching."""
    try:
        if not isinstance(data, dict):
            return
        own = _orig(identity)
        own_new = _nick(identity)
        if 'avatars' in data and isinstance(data['avatars'], dict):
            for avatar_id, avatar_data in data['avatars'].items():
                if not isinstance(avatar_data, dict):
                    continue
                # Mask only display-facing fields. Keep internal identity fields
                # such as name/realName/fakeName intact so the UI can still
                # distinguish one player row from another.
                for key in ('userName', 'displayName', 'fullName'):
                    val = avatar_data.get(key)
                    if val and val != own and val != own_new:
                        avatar_data[key] = _HIDDEN_ALIAS
                for ck in _CLAN_ATTRS:
                    if ck in avatar_data:
                        cur = avatar_data.get(ck, '')
                        if cur and cur != _clan(identity):
                            avatar_data[ck] = _HIDDEN_CLAN
        for key in ('players', 'vehicles', 'personal', 'common'):
            if key in data and isinstance(data[key], dict):
                for pid, pdata in data[key].items():
                    if not isinstance(pdata, dict):
                        continue
                    for nkey in _DISPLAY_NAME_KEYS:
                        val = pdata.get(nkey)
                        if val and val != own and val != own_new:
                            pdata[nkey] = _HIDDEN_ALIAS
                    for ck in _CLAN_ATTRS:
                        val = pdata.get(ck)
                        if val and val != _clan(identity):
                            pdata[ck] = _HIDDEN_CLAN
    except Exception as e:
        logger.error("mask_all_nicknames_in_results error: %s" % e)
