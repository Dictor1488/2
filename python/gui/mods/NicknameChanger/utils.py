import logging
import os
import types
import weakref

logger = logging.getLogger('NicknameChanger')
logger.setLevel(logging.DEBUG if os.path.isfile('.debug_mods') else logging.ERROR)


def make_weak_callback(obj, method_name, *args):
    ref = weakref.ref(obj)

    def _cb():
        instance = ref()
        if instance is None:
            return
        method = getattr(instance, method_name, None)
        if method is None:
            logger.debug("weak_callback: '%s' missing on %s" % (method_name, type(instance).__name__))
            return
        method(*args)

    return _cb


def safe_do(func, label):
    try:
        return func()
    except ImportError as e:
        logger.debug("%s not available: %s" % (label, e))
        return False
    except Exception as e:
        logger.error("Error in %s: %s" % (label, e))
        return False


def try_imports(*import_funcs):
    for func in import_funcs:
        try:
            result = func()
            if result is not None:
                return result
        except (ImportError, AttributeError):
            continue
    return None


_NAME_KEYS = frozenset(('name', 'userName', 'realName', 'fakeName', 'displayName', 'fullName'))
_CLAN_KEYS = frozenset(('clanAbbrev', 'clanTag'))
_MAX_RECURSION_DEPTH = 15


def replace_all_in_dict(data, original_name, new_name, new_clan=None, _visited=None, _depth=0):
    """Recursively replace name/clan in nested dict/list structures."""
    if _depth > _MAX_RECURSION_DEPTH or data is None:
        return
    if _visited is None:
        _visited = set()

    obj_id = id(data)
    if obj_id in _visited:
        return
    _visited.add(obj_id)

    if isinstance(data, dict):
        is_target = False
        for k in _NAME_KEYS:
            v = data.get(k)
            if v == original_name or v == new_name:
                is_target = True
                break

        for key, value in data.items():
            if key in _NAME_KEYS and value == original_name:
                data[key] = new_name
            elif is_target and new_clan and key in _CLAN_KEYS:
                data[key] = new_clan
            elif isinstance(value, (dict, list)):
                replace_all_in_dict(value, original_name, new_name, new_clan, _visited, _depth + 1)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                replace_all_in_dict(item, original_name, new_name, new_clan, _visited, _depth + 1)


def format_full_name(nickname, clan_tag):
    return '%s [%s]' % (nickname, clan_tag) if clan_tag else nickname


_overrides = []


def override(holder, name, wrapper=None, setter=None):
    """Decorator that replaces holder.name with a wrapper.

    Wrapper signature: (baseMethod, baseObject, *args, **kwargs)
    Original methods are stored for restore_overrides().
    Handles regular methods, properties, module-level functions and staticmethods.
    """
    if wrapper is None:
        return lambda wrapper, setter=None: override(holder, name, wrapper, setter)

    if not hasattr(holder, name):
        logger.debug("override: %s missing %s" % (holder, name))
        return None

    target = getattr(holder, name)
    _overrides.append((holder, name, target))

    wrapped = lambda *a, **kw: wrapper(target, *a, **kw)

    if not isinstance(holder, types.ModuleType) and isinstance(target, types.FunctionType):
        setattr(holder, name, staticmethod(wrapped))
    elif isinstance(target, property):
        prop_getter = lambda *a, **kw: wrapper(target.fget, *a, **kw)
        prop_setter = (lambda *a, **kw: setter(target.fset, *a, **kw)) if setter else target.fset
        setattr(holder, name, property(prop_getter, prop_setter, target.fdel))
    else:
        setattr(holder, name, wrapped)

    logger.debug("override: %s.%s installed" % (
        getattr(holder, '__name__', holder), name))
    return wrapped


def restore_overrides():
    count = 0
    while _overrides:
        holder, name, original = _overrides.pop()
        try:
            setattr(holder, name, original)
            count += 1
        except Exception as e:
            logger.debug("restore %s.%s failed: %s" % (holder, name, e))
    logger.debug("restored %d overrides" % count)
    return count
