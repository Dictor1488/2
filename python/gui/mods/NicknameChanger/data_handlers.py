# -*- coding: utf-8 -*-

from .utils import logger, replace_all_in_dict, format_full_name
from .platoon_tracker import platoon_tracker

_HIDDEN_ALIAS = u"???"
_HIDDEN_CLAN = u""

_NAME_KEYS = frozenset(("userName", "displayName", "fullName", "playerName", "name"))
_DISPLAY_NAME_KEYS = frozenset(("userName", "displayName", "fullName", "playerName", "name"))

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
    if _nick(identity):
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


def patch_vo_dict(playerVO, identity):
    """
    Patch a player VO dict in place.
    Used by lobby PRB entities.
    """
    if not playerVO or not identity.has_original:
        return playerVO

    uname = playerVO.get('userName', '')

    if uname == _orig(identity):
        playerVO['userName'] = _nick(identity)
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

    _strip_badges_deep(playerVO)
    return playerVO


def patch_raw_results(result, identity):
    """
    Deep-patch a battle results dict.
    Marks the dict to avoid repeat work.
    """
    if not result or not identity.has_original:
        return

    if isinstance(result, dict):
        if result.get(_RESULTS_PATCHED_MARKER):
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

    # Do not mask avatar internals in hide_all mode.
    # Battle Results UI uses
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

        if patched:
            logger.debug("Patched PlayerInfo for dbID=%s" % dbID)
        return

        # Do not mask PlayerInfo internals in hide_all mode.
        # The battle
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
                for key in ('name', 'userName', 'realName', 'fakeName', 'displayName', 'fullName', 'playerName'):
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

        if hasattr(view_instance, '_personalInfo') and view_instance._personalInfo:
            patch_personal_info_data(view_instance._personalInfo, identity)

        if hasattr(view_instance, '_results') and isinstance(view_instance._results, dict):
            _strip_badges_deep(view_instance._results)

    except Exception as e:
        logger.error("battle_results view patch error: %s" % e)


def mask_all_nicknames_in_results(data, identity):
    """
    hide_all:
      - свой игрок = universal nickname из конфига
      - остальные = Player 1..15
      - внутренние identity-поля не ломаем
    """
    try:
        if not isinstance(data, dict):
            return

        own = _orig(identity)
        own_alias = _nick(identity)
        own_full = format_full_name(own_alias, _clan(identity) or u'')
        own_names = _own_display_names(identity)

        alias_map = {}
        next_idx = [1]

        def get_alias(raw_name):
            if not raw_name or raw_name == own:
                return own_alias

            alias = alias_map.get(raw_name)
            if alias is None:
                alias = _ALIAS_TEMPLATE % next_idx[0]
                alias_map[raw_name] = alias
                next_idx[0] += 1
            return alias

        if 'avatars' in data and isinstance(data['avatars'], dict):
            for avatar_id, avatar_data in data['avatars'].items():
                if not isinstance(avatar_data, dict):
                    continue

                raw_name = (
                    avatar_data.get('name') or
                    avatar_data.get('playerName') or
                    avatar_data.get('realName') or
                    avatar_data.get('fakeName') or
                    avatar_data.get('userName') or
                    avatar_data.get('displayName') or
                    avatar_data.get('fullName')
                )

                if raw_name == own:
                    avatar_data['userName'] = own_alias
                    avatar_data['displayName'] = own_alias
                    avatar_data['fullName'] = own_full
                    for ck in _CLAN_ATTRS:
                        if ck in avatar_data:
                            avatar_data[ck] = _clan(identity) or _HIDDEN_CLAN
                elif raw_name:
                    alias = get_alias(raw_name)
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
                    pdata.get('playerName') or
                    pdata.get('realName') or
                    pdata.get('fakeName') or
                    pdata.get('userName') or
                    pdata.get('displayName') or
                    pdata.get('fullName')
                )

                if raw_name in own_names or raw_name == own:
                    pdata['userName'] = own_alias
                    if 'displayName' in pdata:
                        pdata['displayName'] = own_alias
                    if 'fullName' in pdata:
                        pdata['fullName'] = own_full
                    for ck in _CLAN_ATTRS:
                        if ck in pdata:
                            pdata[ck] = _clan(identity) or _HIDDEN_CLAN
                elif raw_name:
                    alias = get_alias(raw_name)
                    for nkey in _DISPLAY_NAME_KEYS:
                        if nkey in pdata:
                            pdata[nkey] = alias
                    for ck in _CLAN_ATTRS:
                        if ck in pdata:
                            pdata[ck] = _HIDDEN_CLAN

                _strip_badges_deep(pdata)

    except Exception as e:
        logger.error("mask_all_nicknames_in_results error: %s" % e)
