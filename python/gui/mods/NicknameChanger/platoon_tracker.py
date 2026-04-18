"""
Tracks which players are in your platoon (squad) so their nicknames
and clan tags are hidden from the UI, replaced with '???'.

Usage:
    from .platoon_tracker import platoon_tracker

    if platoon_tracker.is_platoon_mate(name):
        alias = platoon_tracker.get_alias(name)  # -> u'???'
"""

from .utils import logger

try:
    unicode
except NameError:
    unicode = str

PLATOON_MATE_ALIAS = u'???'


class PlatoonTracker(object):
    """
    Maintains a set of platoon-mate names.
    Every platoon mate is replaced with the same '???' placeholder.
    """

    def __init__(self):
        self._names = set()   # original nicknames of platoon mates

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self):
        self._names.clear()
        logger.debug("PlatoonTracker: reset")

    def update_from_members(self, members, own_name=None):
        """
        Feed a list/dict of member descriptors.

        Accepts several formats that WoT uses internally:
          - list of dicts with 'name'/'userName' key
          - dict of {accountID: info_dict}
          - list of objects with .name / .userName attribute
        """
        new_names = set()

        if isinstance(members, dict):
            items = members.values()
        else:
            items = members

        for m in items:
            name = self._extract_name(m)
            if name and name != own_name:
                new_names.add(unicode(name))

        added   = new_names - self._names
        removed = self._names - new_names

        for n in removed:
            self._names.discard(n)
            logger.debug("PlatoonTracker: removed %r" % n)

        for n in added:
            self._names.add(n)
            logger.debug("PlatoonTracker: added %r -> %s" % (n, PLATOON_MATE_ALIAS))

    def add_by_name(self, name, own_name=None):
        """Add a single name (used by hooks that see names one at a time)."""
        if not name or name == own_name:
            return
        name = unicode(name)
        if name not in self._names:
            self._names.add(name)
            logger.debug("PlatoonTracker: added (single) %r -> %s" % (name, PLATOON_MATE_ALIAS))

    def is_platoon_mate(self, name):
        return bool(name) and unicode(name) in self._names

    def get_alias(self, name):
        """Return '???' for any known platoon mate, else the original name."""
        if self.is_platoon_mate(name):
            return PLATOON_MATE_ALIAS
        return unicode(name) if name else name

    def __len__(self):
        return len(self._names)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_name(member):
        if isinstance(member, dict):
            return member.get('userName') or member.get('name') or member.get('nickName')
        for attr in ('userName', 'name', 'nickName'):
            val = getattr(member, attr, None)
            if val:
                return val
        return None


platoon_tracker = PlatoonTracker()
