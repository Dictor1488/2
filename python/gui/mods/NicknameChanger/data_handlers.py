# -*- coding: utf-8 -*-

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
_ALIAS_TEMPLATE = u'Player %d'

_BADGE_KEYS = (
    'badge', 'badges', 'badgeLabel', 'badgeType',
    'prefixBadge', 'suffixBadge', 'suffixBadgeType',
    'dogTag', 'dogTags', 'dogTagInfo',
    'rankBadge', 'prestigeMark', 'insignia', 'insignias',
    'patch', 'patches', 'emblem', 'emblems'
)


def _orig(identity):
    return identity.original_name


def _nick(identity):
    return identity.new_name


def _clan(identity):
    return identity.new_clan


def _is_hide_all():
    from .settings import settings
    return settings.enabled and settings.hide_all_nicknames


def _own_display_names(identity):
    names = set()
    if _orig(identity):
        names.add(_orig(identity))
    if _nick(identity):
        names.add(_nick(identity))
        names.add(format_full_name(_nick(identity), _clan(identity) or u''))
    return names


def _strip_badges_deep(node):
    try:
        if isinstance(node, dict):
            lowered_badge_keys = tuple(k.lower() for k in _BADGE_KEYS)
            for key in list(node.keys()):
                low = key.lower()
                if (
                    low in lowered_badge_keys or
                    'badge' in low or
                    'dogtag' in low or
                    'insign' in low or
                    'patch' in low or
                    'emblem' in low
                ):
                    value = node.get(key)
                    if isinstance(value, list):
                        node[key] = []
                    elif isinstance(value, dict):
                        node[key] = {}
                    else:
                        node[key] = None
                    continue
                _strip_badges_deep(node[key])
        elif isinstance(node, list):
            for item in node:
                _strip_badges_deep(item)
    except Exception as e:
        logger.debug("badge strip error: %s" % e)


def _build_alias_maps(data, identity):
    own_names = _own_display_names(identity)
    by_name = {}
    by_id = {}
    next_idx = [1]

    def claim(name=None, pid=None):
        key_id = pid if pid not in (None, '') else None
        key_name = name if name not in (None, '') else None

        if key_name in own_names or key_name == _orig(identity):
            alias = _nick(identity)
        elif key_id is not None and key_id in by_id:
            alias = by_id[key_id]
        elif key_name is not None and key_name in by_name:
            alias = by_name[key_name]
        else:
            alias = _ALIAS_TEMPLATE % next_idx[0]
            next_idx[0] += 1

        if key_id is not None:
            by_id[key_id] = alias
        if key_name is not None:
            by_name[key_name] = alias
        return alias

    if not isinstance(data, dict):
        return by_name, by_id

    for bucket_name in ('avatars', 'players', 'vehicles', 'personal', 'common'):
        bucket = data.get(bucket_name)
        if not isinstance(bucket, dict):
            continue
        for pid, pdata in bucket.items():
            if not isinstance(pdata, dict):
                continue
            raw_name = (
                pdata.get('name') or
                pdata.get('realName') or
                pdata.get('fakeName') or
                pdata.get('userName') or
                pdata.get('displayName') or
                pdata.get('fullName')
            )
            claim(raw_name, pid)

    return by_name, by_id


def _alias_for(name, pid, identity, by_name, by_id):
    own_names = _own_display_names(identity)
    if name in own_names or name == _orig(identity):
        return _nick(identity)
    if pid not in (None, '') and pid in by_id:
        return by_id[pid]
    if name not in (None, '') and name in by_name:
        return by_name[name]
    return None


def patch_vo_dict(playerVO, identity):
    if not playerVO or not identity.has_original:
        return playerVO

    uname = playerVO.get('userName', '')

    if uname == _orig(identity):
        playerVO['userName'] = _nick(identity)
        playerVO['displayName'] = _nick(identity)
        if _clan(identity):
            playerVO['clanAbbrev'] = _clan(identity)
        playerVO['fullName'] = format_full_name(
            _nick(identity),
            _clan(identity) or playerVO.get('clanAbbrev', '')
        )
        logger.debug("Patched playerVO userName")

    elif _clan(identity) and uname == _nick(identity):
        playerVO['clanAbbrev'] = _clan(identity)
        playerVO['fullName'] = format_full_name(_nick(identity), _clan(identity))
        playerVO['displayName'] = _nick(identity)

    elif uname and platoon_tracker.is_platoon_mate(uname):
        alias = platoon_tracker.get_alias(uname)
        playerVO['userName'] = alias
        playerVO['displayName'] = alias
        playerVO['clanAbbrev'] = _HIDDEN_CLAN
        playerVO['fullName'] = alias
        logger.debug("Patched platoon mate playerVO: %s -> %s" % (uname, alias))

    elif uname and _is_hide_all() and uname != _orig(identity):
        playerVO['userName'] = _HIDDEN_ALIAS
        playerVO['displayName'] = _HIDDEN_ALIAS
        playerVO['clanAbbrev'] = _HIDDEN_CLAN
        playerVO['fullName'] = _HIDDEN_ALIAS
        logger.debug("hide_all: masked playerVO userName %s" % uname)

    _strip_badges_deep(playerVO)
    return playerVO


def patch_raw_results(result, identity):
    if not result or not identity.has_original:
        return

    if isinstance(result, dict) and result.get(_RESULTS_PATCHED_MARKER):
        return

    patch_battle_results_avatars(result, identity)

    replace_all_in_dict(
        result,
        _orig(identity),
        _nick(identity),
        _clan(identity) if _clan(identity) else None
    )

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
            if hasattr(personal_info.avatar, 'userName'):
                personal_info.avatar.userName = _nick(identity)
            if hasattr(personal_info.avatar, 'displayName'):
                personal_info.avatar.displayName = _nick(identity)
            if hasattr(personal_info.avatar, 'fullName'):
                personal_info.avatar.fullName = format_full_name(_nick(identity), _clan(identity) or u'')
            logger.debug("Patched personal_info.avatar.name")

        if _clan(identity) and hasattr(personal_info.avatar, 'clanAbbrev'):
            personal_info.avatar.clanAbbrev = _clan(identity)

    except Exception as e:
        logger.error("personal_info patch error: %s" % e)


def patch_reusable_info_deep(reusableInfo, identity):
    try:
        alias_name_map = getattr(reusableInfo, '_nc_alias_name_map', {})
        alias_id_map = getattr(reusableInfo, '_nc_alias_id_map', {})

        if hasattr(reusableInfo, 'personal') and reusableInfo.personal:
            if hasattr(reusableInfo.personal, 'avatar'):
                _patch_avatar_attrs(reusableInfo.personal.avatar, identity, "personal.avatar", None, alias_name_map, alias_id_map)

        if hasattr(reusableInfo, 'common') and hasattr(reusableInfo.common, 'avatars'):
            for avatar_id, avatarInfo in reusableInfo.common.avatars.items():
                _patch_avatar_attrs(avatarInfo, identity, "common.avatar[%s]" % avatar_id, avatar_id, alias_name_map, alias_id_map)

    except Exception as e:
        logger.error("reusable_info deep patch error: %s" % e)


def _patch_avatar_attrs(avatar, identity, label, avatar_id=None, alias_name_map=None, alias_id_map=None):
    try:
        alias_name_map = alias_name_map or {}
        alias_id_map = alias_id_map or {}

        raw_name = None
        for attr in _PLAYER_INFO_ATTRS:
            if hasattr(avatar, attr):
                value = getattr(avatar, attr)
                if value:
                    raw_name = value
                    break

        is_own = raw_name in _own_display_names(identity) or raw_name == _orig(identity)
        alias = _alias_for(raw_name, avatar_id, identity, alias_name_map, alias_id_map)

        if is_own:
            final_name = _nick(identity)
            full_name = format_full_name(_nick(identity), _clan(identity) or u'')
            for attr in _PLAYER_INFO_ATTRS:
                if hasattr(avatar, attr):
                    setattr(avatar, attr, full_name if attr == 'fullName' else final_name)
            if _clan(identity):
                for clan_attr in _CLAN_ATTRS:
                    if hasattr(avatar, clan_attr):
                        setattr(avatar, clan_attr, _clan(identity))
        elif _is_hide_all() and alias:
            for attr in _PLAYER_INFO_ATTRS:
                if hasattr(avatar, attr):
                    setattr(avatar, attr, alias)
            for clan_attr in _CLAN_ATTRS:
                if hasattr(avatar, clan_attr):
                    setattr(avatar, clan_attr, _HIDDEN_CLAN)

        _strip_badges_deep(getattr(avatar, '__dict__', {}))
    except Exception as e:
        logger.error("avatar patch error for %s: %s" % (label, e))


def patch_reusable_info_players(reusableInfo, identity):
    try:
        if not hasattr(reusableInfo, 'players'):
            return

        results = getattr(reusableInfo, '_results', None)
        alias_name_map = {}
        alias_id_map = {}
        if isinstance(results, dict):
            alias_name_map, alias_id_map = _build_alias_maps(results, identity)
        reusableInfo._nc_alias_name_map = alias_name_map
        reusableInfo._nc_alias_id_map = alias_id_map

        players = reusableInfo.players
        if hasattr(players, 'getPlayerInfoIterator'):
            for dbID, playerInfo in players.getPlayerInfoIterator():
                _patch_player_info(playerInfo, identity, dbID, alias_name_map, alias_id_map)
        elif hasattr(players, 'items'):
            for dbID, playerInfo in players.items():
                _patch_player_info(playerInfo, identity, dbID, alias_name_map, alias_id_map)

    except Exception as e:
        logger.error("reusable_info players patch error: %s" % e)


def _patch_player_info(playerInfo, identity, dbID, alias_name_map=None, alias_id_map=None):
    try:
        alias_name_map = alias_name_map or {}
        alias_id_map = alias_id_map or {}

        raw_name = None
        for attr in _PLAYER_INFO_ATTRS:
            if hasattr(playerInfo, attr):
                value = getattr(playerInfo, attr)
                if value:
                    raw_name = value
                    break

        if not raw_name:
            for attr in _PRIVATE_NAME_ATTRS:
                if hasattr(playerInfo, attr):
                    value = getattr(playerInfo, attr)
                    if value:
                        raw_name = value
                        break

        is_own = raw_name in _own_display_names(identity) or raw_name == _orig(identity)
        alias = _alias_for(raw_name, dbID, identity, alias_name_map, alias_id_map)

        if is_own:
            for attr in _PLAYER_INFO_ATTRS:
                if hasattr(playerInfo, attr):
                    setattr(playerInfo, attr, format_full_name(_nick(identity), _clan(identity) or u'') if attr == 'fullName' else _nick(identity))
            for attr in _PRIVATE_NAME_ATTRS:
                if hasattr(playerInfo, attr):
                    setattr(playerInfo, attr, _nick(identity))
            if _clan(identity):
                for attr in _CLAN_ATTRS + _PRIVATE_CLAN_ATTRS:
                    if hasattr(playerInfo, attr):
                        setattr(playerInfo, attr, _clan(identity))
            logger.debug("Patched PlayerInfo for dbID=%s" % dbID)
            return

        if _is_hide_all() and alias:
            for attr in _PLAYER_INFO_ATTRS:
                if hasattr(playerInfo, attr):
                    setattr(playerInfo, attr, alias)
            for attr in _PRIVATE_NAME_ATTRS:
                if hasattr(playerInfo, attr):
                    setattr(playerInfo, attr, alias)
            for attr in _CLAN_ATTRS + _PRIVATE_CLAN_ATTRS:
                if hasattr(playerInfo, attr):
                    setattr(playerInfo, attr, _HIDDEN_CLAN)
            _strip_badges_deep(getattr(playerInfo, '__dict__', {}))

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

                if name_patched:
                    avatar_data['displayName'] = _nick(identity)
                    avatar_data['fullName'] = format_full_name(_nick(identity), _clan(identity) or u'')
                    if _clan(identity):
                        for ck in _CLAN_ATTRS:
                            if ck in avatar_data:
                                avatar_data[ck] = _clan(identity)

        for key in ('players', 'vehicles', 'personal', 'common'):
            if key in data and isinstance(data[key], (dict, list)):
                replace_all_in_dict(
                    data[key],
                    _orig(identity),
                    _nick(identity),
                    _clan(identity) if _clan(identity) else None
                )

    except Exception as e:
        logger.error("battle_results avatars patch error: %s" % e)


def patch_battle_results_view(view_instance, identity):
    try:
        if hasattr(view_instance, '_reusableInfo') and view_instance._reusableInfo:
            patch_reusable_info_players(view_instance._reusableInfo, identity)
            patch_reusable_info_deep(view_instance._reusableInfo, identity)

        if hasattr(view_instance, '_personalInfo') and view_instance._personalInfo:
            patch_personal_info_data(view_instance._personalInfo, identity)

        if hasattr(view_instance, '_results') and isinstance(view_instance._results, dict):
            mask_all_nicknames_in_results(view_instance._results, identity)
            _strip_badges_deep(view_instance._results)

    except Exception as e:
        logger.error("battle_results view patch error: %s" % e)


def mask_all_nicknames_in_results(data, identity):
    try:
        if not isinstance(data, dict):
            return

        own = _orig(identity)
        own_alias = _nick(identity)
        own_full = format_full_name(own_alias, _clan(identity) or u'')
        own_names = _own_display_names(identity)

        alias_name_map, alias_id_map = _build_alias_maps(data, identity)

        if 'avatars' in data and isinstance(data['avatars'], dict):
            for avatar_id, avatar_data in data['avatars'].items():
                if not isinstance(avatar_data, dict):
                    continue

                raw_name = (
                    avatar_data.get('name') or
                    avatar_data.get('realName') or
                    avatar_data.get('fakeName') or
                    avatar_data.get('userName') or
                    avatar_data.get('displayName')
                )
                alias = _alias_for(raw_name, avatar_id, identity, alias_name_map, alias_id_map)

                if raw_name in own_names or raw_name == own:
                    avatar_data['name'] = own_alias
                    avatar_data['userName'] = own_alias
                    avatar_data['displayName'] = own_alias
                    avatar_data['fullName'] = own_full
                    for ck in _CLAN_ATTRS:
                        if ck in avatar_data:
                            avatar_data[ck] = _clan(identity) or _HIDDEN_CLAN
                elif alias:
                    avatar_data['name'] = alias
                    avatar_data['userName'] = alias
                    avatar_data['displayName'] = alias
                    avatar_data['fullName'] = alias
                    for ck in _CLAN_ATTRS:
                        if ck in avatar_data:
                            avatar_data[ck] = _HIDDEN_CLAN

                _strip_badges_deep(avatar_data)

        for key in ('players', 'vehicles', 'personal', 'common'):
            block = data.get(key)
            if not isinstance(block, dict):
                continue

            for pid, pdata in block.items():
                if not isinstance(pdata, dict):
                    continue

                raw_name = (
                    pdata.get('name') or
                    pdata.get('realName') or
                    pdata.get('fakeName') or
                    pdata.get('userName') or
                    pdata.get('displayName') or
                    pdata.get('fullName')
                )
                alias = _alias_for(raw_name, pid, identity, alias_name_map, alias_id_map)

                if raw_name in own_names or raw_name == own:
                    pdata['name'] = own_alias
                    pdata['userName'] = own_alias
                    pdata['displayName'] = own_alias
                    pdata['fullName'] = own_full
                    for ck in _CLAN_ATTRS:
                        if ck in pdata:
                            pdata[ck] = _clan(identity) or _HIDDEN_CLAN
                elif alias:
                    pdata['name'] = alias
                    pdata['userName'] = alias
                    pdata['displayName'] = alias
                    pdata['fullName'] = alias
                    for ck in _CLAN_ATTRS:
                        if ck in pdata:
                            pdata[ck] = _HIDDEN_CLAN

                _strip_badges_deep(pdata)

    except Exception as e:
        logger.error("mask_all_nicknames_in_results error: %s" % e)
