import random

from .cache import CacheManagerBase
from .translations import Translator, createTooltip
from .utils import logger

SETTINGS_PATH = 'mods/configs/under_pressure/NicknameChanger/settings.json'
SETTINGS_VERSION = 1
DEFAULT_NICKNAME = u'BOSS'
DEFAULT_CLAN_TAG = u'ELITE'

try:
    unicode
except NameError:
    unicode = str


class SettingsHolder(CacheManagerBase):

    def __init__(self):
        super(SettingsHolder, self).__init__(
            path=SETTINGS_PATH, version=SETTINGS_VERSION, name='settings')
        self.data = {
            'enable': True,
            'nickname': DEFAULT_NICKNAME,
            'clan_tag': DEFAULT_CLAN_TAG,
            'hide_all_nicknames': False,
        }
        self._listeners = []
        loaded = self.load()
        if not loaded:
            self.save()

    def to_dict(self):
        return dict(self.data)

    def from_dict(self, data):
        for key in self.data.keys():
            if key in data:
                self.data[key] = data[key]

    def __call__(self, key):
        return self.data.get(key)

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        if key in self.data and self.data[key] != value:
            self.data[key] = value
            self.save()

    def update(self, new_data):
        changed = False
        for key, value in new_data.items():
            if key in self.data and self.data[key] != value:
                self.data[key] = value
                changed = True
        if changed:
            self.save()
            self._notify()

    def subscribe(self, listener):
        if listener not in self._listeners:
            self._listeners.append(listener)

    def _notify(self):
        for fn in list(self._listeners):
            try:
                fn()
            except Exception as e:
                logger.error("Settings listener error: %s" % e)

    @property
    def enabled(self):
        return bool(self.data.get('enable'))

    @property
    def nickname(self):
        return unicode(self.data.get('nickname') or DEFAULT_NICKNAME)

    @property
    def clan_tag(self):
        return unicode(self.data.get('clan_tag') or u"")

    @property
    def hide_all_nicknames(self):
        return bool(self.data.get('hide_all_nicknames'))


settings = SettingsHolder()


def _make_checkbox(templates, label, var_name, value, tooltip=None):
    creators = (
        getattr(templates, 'createCheckBox', None),
        getattr(templates, 'createCheckbox', None),
        getattr(templates, 'createControl', None),
    )
    for creator in creators:
        if creator is None:
            continue
        try:
            if creator.__name__ == 'createControl':
                return creator('CheckBox', label, var_name, value, tooltip=tooltip)
            return creator(label, var_name, value, tooltip=tooltip)
        except TypeError:
            continue
    logger.error('No compatible checkbox creator found in modsSettingsApi templates')
    return None


def _register_mod_settings_api():
    try:
        from gui.modsSettingsApi import g_modsSettingsApi, templates
    except ImportError:
        logger.debug("modsSettingsApi not available")
        return

    linkage_id = 'me.under-pressure.nicknamechanger'

    checkbox = _make_checkbox(
        templates,
        Translator.HIDE_ALL_HEADER,
        'hide_all_nicknames',
        settings('hide_all_nicknames'),
        tooltip=createTooltip(
            header=Translator.HIDE_ALL_HEADER,
            body=Translator.HIDE_ALL_BODY))

    template = {
        'modDisplayName': Translator.MOD_NAME,
        'enabled': settings('enable'),
        'column1': [
            templates.createInput(
                Translator.NICKNAME_HEADER,
                'nickname',
                settings('nickname'),
                tooltip=createTooltip(
                    header=Translator.NICKNAME_HEADER,
                    body=Translator.NICKNAME_BODY)),
            templates.createInput(
                Translator.CLAN_TAG_HEADER,
                'clan_tag',
                settings('clan_tag'),
                tooltip=createTooltip(
                    header=Translator.CLAN_TAG_HEADER,
                    body=Translator.CLAN_TAG_BODY)),
        ],
        'column2': [item for item in [checkbox] if item is not None],
    }

    def on_changed(linkage, new_settings):
        if linkage != linkage_id:
            return
        update = {}
        if 'enabled' in new_settings:
            update['enable'] = new_settings['enabled']
        if 'nickname' in new_settings:
            update['nickname'] = new_settings['nickname']
        if 'clan_tag' in new_settings:
            update['clan_tag'] = new_settings['clan_tag']
        if 'hide_all_nicknames' in new_settings:
            update['hide_all_nicknames'] = new_settings['hide_all_nicknames']
        if update:
            settings.update(update)
            logger.debug("Settings updated via UI: %s" % update)

    try:
        template_copy = template.copy()
        template_copy['random'] = random.randint(10000, 99999)
        g_modsSettingsApi.setModTemplate(linkage_id, template_copy, on_changed)
        logger.debug("modsSettingsApi template registered")
    except Exception as e:
        logger.error("Failed to register modsSettingsApi: %s" % e)


_register_mod_settings_api()
