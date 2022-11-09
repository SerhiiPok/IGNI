# a utility for managing / loading the witcher game resources from the root folder with resources
from mdb import Mdb
import mdb2fbx

class ResourceType:

    """
    resource type, has a validator which checks if an arbitrary file is of this resource type,
    and a resource loader, which loads resources of this type
    """

    def __init__(self, name, extension, validator=None, loader=None):
        self.name = name
        self.extension = extension

        if validator is None:
            self._user_validator = lambda s: True
        else:
            self._user_validator = validator

        if loader is None:
            self._loader = lambda fpath: open(fpath, 'rb')
        else:
            self._loader = loader

    def validate(self, fpath):
        if not fpath.endswith(self.extension):
            return False
        return self._user_validator(fpath)

    def load_resource_data(self, fpath):
        return self._loader(fpath)

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, ResourceType):
            return False
        else:
            if self.name == other.name:
                return True


class KNOWN_RESOURCE_TYPES:

    MDB = ResourceType(name='mdb',
                       extension='.mdb',
                       validator=lambda fpath: not (any([b != 0 for b in open(fpath, 'rb').read(4)])),
                       loader=lambda fpath: Mdb.from_file(fpath))

    MBA = ResourceType(name='mba',
                       extension='.mdb',
                       validator=lambda fpath: not (any([b != 0 for b in open(fpath, 'rb').read(4)])),
                       loader=lambda fpath: Mdb.from_file(fpath))

    MDBT = ResourceType(name='mdbt',
                        extension='.mdb',
                        validator=lambda fpath: (any([b != 0 for b in open(fpath, 'rb').read(4)])))


def resolve_resource_type(fpath) -> ResourceType:
    return ResourceType()


class Resource:

    def __init__(self, fpath):
        resource_type = resolve_resource_type(fpath)
        self.path = fpath
        self.resource = resource_type.load_resource_data(fpath)

    def get(self):
        return self.resource


class ResourceManager:

    def __init__(self):
        pass

    def get_all_of_type(self, resource_type: ResourceType, filterer=None):
        return []

    def get_all_extensions(self):
        return []

    def get_statistics_by_resource_type(self):
        return {}

    def get_statistics_for_resource_type(self, resource_type: ResourceType):
        return []

    def get_all_prefixes(self):
        return []

    def get(self, name: str, resource_type: ResourceType):
        return None

    def get_by_file_name(self, file_name: str):
        return None

    def get_by_file_name_pattern(self, file_name_pattern: str):
        return []

    def locate(self, file_name: str):
        return ''
