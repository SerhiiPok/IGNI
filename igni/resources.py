# a utility for managing / loading the witcher game resources from the root folder with resources
import ntpath
import re

from mdb import Mdb
import mdb2fbx
import os
import ntpath


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


class ResourceTypes:

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


class FileSystem:

    """
    caches directories
    """

    def __init__(self):
        self.directories = []

    def get_directory(self, directory):
        # try to return cached data
        if directory in self.directories:
            return self.directories[self.directories.index(directory)]
        else:
            return directory


FILE_SYSTEM = FileSystem()


class File:

    def __init__(self, full_file_path: str):

        self._full_file_path = None
        self.full_file_name = None
        self.file_name = None
        self.file_extension = None
        self.file_name_prefix = None
        self.file_name_suffix = None
        self.file_name_root = None
        self.location: Directory = None

        self._size = None

        self._init_data_(full_file_path)

    def __str__(self):
        return self._full_file_path

    def __hash__(self):
        return hash(str(self))

    @property
    def size(self):
        if self._size is None:
            self._size = os.path.getsize(self._full_file_path)
        return self._size

    def _init_data_(self, full_file_path: str):

        if os.path.exists(full_file_path) and os.path.isfile(full_file_path):
            self._full_file_path = full_file_path
        else:
            raise Exception('file path "{}" is invalid'.format(full_file_path))

        _path, _fname = ntpath.split(full_file_path)

        self.location = FILE_SYSTEM.get_directory(Directory(_path))

        name_and_extension = _fname.split('.')
        self.name = name_and_extension[0]
        if len(name_and_extension) > 1:
            self.extension = name_and_extension[1]
        if len(name_and_extension) > 2:
            raise Exception('invalid file name supplied: {}'.format(_fname))

        prefix_root_suffix = self.name.split('_')
        if len(prefix_root_suffix) == 1:
            self.name_root = prefix_root_suffix[0]
        else:
            self.name_root = prefix_root_suffix[1]
            self.name_prefix = prefix_root_suffix[0]

        if len(prefix_root_suffix) > 2:
            self.name_suffix = prefix_root_suffix[len(prefix_root_suffix)-1]


class Directory:

    def __init__(self, full_directory_path: str):
        if os.path.exists(full_directory_path) and os.path.isdir(full_directory_path):
            self.full_path = full_directory_path
        else:
            raise Exception('invalid directory path {}'.format(full_directory_path))

        self._dir_contents = None
        self._files = None  # of type _FilePath, lazy, caching
        self._subdirectories = None  # of type _Directory, lazy, caching

    def __str__(self):
        return self.full_path

    def __hash__(self):
        return hash(str(self))

    def _init_data_(self):
        self._dir_contents = [os.path.join(self.full_path, file_name) for file_name in os.listdir(self.full_path)]
        self._files = [File(f) for f in self.dir_contents if os.path.isfile(f)]

        # reuse cached directories if possible
        self._subdirs = [FILE_SYSTEM.get_directory(Directory(f)) for f in self.dir_contents if os.path.isdir(f)]

    @property
    def files(self):
        if self._files is None:
            self._init_data_()
            return self._files
        else:
            return self._files

    @property
    def subdirectories(self):
        if self._subdirectories is None:
            self._init_data_()
            return self._subdirectories
        else:
            return self._subdirectories

    def collect_files(self):
        results = []

        def _collect_recursively_(directory: Directory, out: list):
            out.extend(directory.files)
            for subdir in directory.subdirectories:
                _collect_recursively_(subdir, out)

        _collect_recursively_(self, results)
        return results

    def locate(self, full_file_name: str) -> File:
        if self._dir_contents is None:
            self._init_data_()

        if full_file_name in self._dir_contents:
            return File(os.path.join(self.full_path, full_file_name))

    def search(self, name_or_regex, subdirs=True):

        results = []

        def _search(in_directory: Directory) -> list:
            if isinstance(name_or_regex, str):
                found = in_directory.locate(name_or_regex)
                if found is not None:
                    return [found]
                else:
                    return []
            elif isinstance(name_or_regex, re.Pattern):
                return [File(os.path.join(in_directory.full_path, fpath.full_file_name))
                        for fpath in in_directory.files if name_or_regex.match(fpath.full_file_name)]

        def _recursive_search(start: Directory, out: list):
            out.extend(_search(start))
            for subdir in start.subdirectories:
                _recursive_search(subdir, out)

        if subdirs:
            _recursive_search(self, results)
        else:
            _search(self)

        return results

    def list_extensions(self):
        return list(set([filepath.extension for filepath in self.files]))


class ResourceManager:

    def __init__(self, root_dir):
        self.root_directory = Directory(root_dir)
        self.files = self.root_directory.collect_files()

    def get_all_of_type(self, resource_type: ResourceType, filterer=None):
        resources = [Resource(str(file)) for file in self.files if resource_type.validate(str(file))]
        if filterer is not None:
            resources = [resource for resource in resources if filterer(resource)]
        return resources

    def locate_all_of_type(self, resource_type: ResourceType):
        return [file for file in self.files if resource_type.validate(str(file))]

    def get_all_extensions(self):
        return list(set([f.extension for f in self.files]))

    def get_statistics_by_resource_type(self):
        return {}

    def get_statistics_for_resource_type(self, resource_type: ResourceType):
        return []

    def get_all_prefixes(self, resource_type: ResourceType = None):
        if resource_type is not None:
            files = self.locate_all_of_type(resource_type)
        else:
            files = self.files

        return list(set([file.file_name_prefix for file in files]))

    def get(self, name: str, resource_type: ResourceType) -> Resource:
        results = [f for f in self.files if f.full_file_name == name and resource_type.validate(str(f))]
        if len(results) > 1:
            raise Exception('more than one resource with name {} and type {} was found'.format(name, resource_type.name))

        if len(results) > 0:
            return Resource(results[0])

    def get_by_file_name(self, file_name: str):
        return [Resource(file) for file in self.files if file.full_file_name == file_name]

    def get_by_file_name_pattern(self, file_name_pattern: re.Pattern):
        return [Resource(file) for file in self.root_directory.search(file_name_pattern)]
