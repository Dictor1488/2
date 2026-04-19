# -*- coding: utf-8 -*-

from .utils import logger, format_full_name
from .platoon_tracker import platoon_tracker

_HIDDEN_ALIAS = u"???"
_HIDDEN_CLAN = u""

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

_DISPLAY_KEYS = ('userName', 'displayName', 'fullName')


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


def _strip_badges_shallow(node):
    if not isinstance(node, dict):
        return

    for key in list(node.keys()):
        low = key.lower()
        if (
            low in tuple(k.lower() for k in _BADGE_KEYS) or
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


def patch_vo_dict(playerVO, identity):
    if not playerVO or not identity.has_original:
        return playerVO

    uname = playerVO.get('userName', '')

    if uname == _orig(identity):
        playerVO['userName'] = _nick(identity)
        playerVO['displayName'] = _nick(identity)
        playerVO['fullName'] = format_full_name(
            _nick(identity),
            _clan(identity) or playerVO.get('clanAbbrev', '')
        )
        if _clan(identity):
            playerVO['clanAbbrev'] = _clan(identity)

    elif uname and platoon_tracker.is_platoon_mate(uname):
        alias = platoon_tracker.get_alias(uname)
        playerVO['userName'] = alias
        playerVO['displayName'] = alias
        playerVO['fullName'] = alias
        playerVO['clanAbbrev'] = _HIDDEN_CLAN

    elif uname and _is_hide_all() and uname != _orig(identity):
        playerVO['userName'] = _HIDDEN_ALIAS
        playerVO['displayName'] = _HIDDEN_ALIAS
        playerVO['fullName'] = _HIDDEN_ALIAS
        playerVO['clanAbbrev'] = _HIDDEN_CLAN

    _strip_badges_shallow(playerVO)
    return playerVO


def patch_raw_results(result, identity):
    """
    Safe patch for battle results.
    Important: do not globally replace values deep in the whole result tree,
    because battle-results UI uses internal player structures for selection.
    """
    if not result or not identity.has_original:
        return

    if isinstance(result, dict) and result.get(_RESULTS_PATCHED_MARKER):
        return

    patch_battle_results_avatars(result, identity)

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

    except Exception as e:
        logger.error("PlayerInfo patch error for dbID=%s: %s" % (dbID, e))


def patch_battle_results_avatars(data, identity):
    try:
        if not isinstance(data, dict):
            return

        avatars = data.get('avatars')
        if isinstance(avatars, dict):
            for avatar_id, avatar_data in avatars.items():
                if not isinstance(avatar_data, dict):
                    continue

                for key in ('name', 'userName', 'realName', 'fakeName', 'displayName'):
                    if avatar_data.get(key) == _orig(identity):
                        avatar_data[key] = _nick(identity)

                if avatar_data.get('fullName') == _orig(identity):
                    avatar_data['fullName'] = format_full_name(_nick(identity), _clan(identity) or u'')

                if _clan(identity):
                    for ck in _CLAN_ATTRS:
                        if avatar_data.get('userName') == _nick(identity) and ck in avatar_data:
                            avatar_data[ck] = _clan(identity)

                _strip_badges_shallow(avatar_data)

    except Exception as e:
        logger.error("battle_results avatars patch error: %s" % e)


def patch_battle_results_view(view_instance, identity):
    try:
        if hasattr(view_instance, '_reusableInfo') and view_instance._reusableInfo:
            patch_reusable_info_players(view_instance._reusableInfo, identity)

        if hasattr(view_instance, '_personalInfo') and view_instance._personalInfo:
            patch_personal_info_data(view_instance._personalInfo, identity)

        # Do not deep-strip the whole _results tree here:
        # that can break battle-results window logic.

    except Exception as e:
        logger.error("battle_results view patch error: %s" % e)


def mask_all_nicknames_in_results(data, identity):
    """
    hide_all:
      - own player = universal nickname from config
      - others = Player 1..15
      - only display fields are changed
      - internal player selection structures stay untouched
    """
    try:
        if not isinstance(data, dict):
            return

        own = _orig(identity)
        own_alias = _nick(identity)
        own_full = format_full_name(own_alias, _clan(identity) or u'')
        own_names = _own_display_names(identity)

        alias_by_key = {}
        next_idx = [1]

        def get_alias(key):
            alias = alias_by_key.get(key)
            if alias is None:
                alias = _ALIAS_TEMPLATE % next_idx[0]
                alias_by_key[key] = alias
                next_idx[0] += 1
            return alias

        avatars = data.get('avatars')
        if isinstance(avatars, dict):
            for avatar_id, avatar_data in avatars.items():
                if not isinstance(avatar_data, dict):
                    continue

                raw_name = (
                    avatar_data.get('name') or
                    avatar_data.get('realName') or
                    avatar_data.get('fakeName') or
                    avatar_data.get('userName') or
                    avatar_data.get('displayName') or
                    avatar_data.get('fullName')
                )

                if raw_name in own_names or raw_name == own:
                    avatar_data['userName'] = own_alias
                    avatar_data['displayName'] = own_alias
                    avatar_data['fullName'] = own_full
                    for ck in _CLAN_ATTRS:
                        if ck in avatar_data:
                            avatar_data[ck] = _clan(identity) or _HIDDEN_CLAN
                elif raw_name:
                    alias = get_alias(('avatar', avatar_id))
                    avatar_data['userName'] = alias
                    avatar_data['displayName'] = alias
                    avatar_data['fullName'] = alias
                    for ck in _CLAN_ATTRS:
                        if ck in avatar_data:
                            avatar_data[ck] = _HIDDEN_CLAN

                _strip_badges_shallow(avatar_data)

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

                if raw_name in own_names or raw_name == own:
                    pdata['userName'] = own_alias
                    pdata['displayName'] = own_alias
                    pdata['fullName'] = own_full
                    for ck in _CLAN_ATTRS:
                        if ck in pdata:
                            pdata[ck] = _clan(identity) or _HIDDEN_CLAN
                elif raw_name:
                    alias = get_alias((key, pid))
                    pdata['userName'] = alias
                    pdata['displayName'] = alias
                    pdata['fullName'] = alias
                    for ck in _CLAN_ATTRS:
                        if ck in pdata:
                            pdata[ck] = _HIDDEN_CLAN

                _strip_badges_shallow(pdata)

    except Exception as e:
        logger.error("mask_all_nicknames_in_results error: %s" % e)
