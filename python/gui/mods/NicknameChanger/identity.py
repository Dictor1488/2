class Identity(object):

    __slots__ = ('_original_name', '_original_clan', '_new_name', '_new_clan')

    def __init__(self):
        self._original_name = None
        self._original_clan = None
        self._new_name = u""
        self._new_clan = u""


    @property
    def original_name(self):
        return self._original_name

    @original_name.setter
    def original_name(self, value):
        self._original_name = value

    @property
    def original_clan(self):
        return self._original_clan

    @original_clan.setter
    def original_clan(self, value):
        self._original_clan = value

    @property
    def has_original(self):
        return bool(self._original_name)


    @property
    def new_name(self):
        return self._new_name

    @property
    def new_clan(self):
        return self._new_clan

    def update_replacement(self, new_name, new_clan):
        self._new_name = new_name or u""
        self._new_clan = new_clan or u""

    @property
    def full_name(self):
        if self._new_clan:
            return u"%s [%s]" % (self._new_name, self._new_clan)
        return self._new_name

    def matches(self, name):
        return bool(self._original_name) and name == self._original_name

    def __repr__(self):
        return "Identity(orig=%r, clan=%r -> new=%r, clan=%r)" % (
            self._original_name, self._original_clan, self._new_name, self._new_clan)
