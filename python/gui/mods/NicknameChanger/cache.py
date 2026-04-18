import io
import os
import json

from .utils import logger


class CacheManagerBase(object):

    def __init__(self, path, version, name):
        self.path = path
        self.version = version
        self.name = name

    def to_dict(self):
        raise NotImplementedError

    def from_dict(self, data):
        raise NotImplementedError

    def save(self):
        try:
            cache_dir = os.path.dirname(self.path)
            if cache_dir and not os.path.isdir(cache_dir):
                os.makedirs(cache_dir)
        except (IOError, OSError) as e:
            logger.error("Failed to create dir for %s cache: %s" % (self.name, e))
            return False

        try:
            content = {"version": self.version, "data": self.to_dict()}
            text = json.dumps(content, indent=4, ensure_ascii=False)
            if isinstance(text, bytes):
                text = text.decode("utf-8")
            with io.open(self.path, "w", encoding="utf-8") as fh:
                fh.write(text)
            logger.debug("%s cache saved" % self.name)
            return True
        except (IOError, TypeError) as e:
            logger.error("Failed to write %s cache: %s" % (self.name, e))
            return False

    def load(self):
        if not os.path.isfile(self.path):
            logger.debug("%s cache not found, will use defaults" % self.name)
            return False
        try:
            with io.open(self.path, "r", encoding="utf-8") as fh:
                raw = fh.read()
            if not raw:
                return False
            content = json.loads(raw)
            if content.get("version") != self.version:
                logger.debug("%s cache version mismatch (%s != %s), ignoring" % (
                    self.name, content.get("version"), self.version))
                return False
            self.from_dict(content.get("data", {}))
            logger.debug("%s cache loaded" % self.name)
            return True
        except (IOError, ValueError) as e:
            logger.error("Failed to read %s cache: %s" % (self.name, e))
            return False
