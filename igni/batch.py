import mdb2fbx
from .resources import Directory, ResourceType, ResourceManager, ResourceTypes, Resource
from .settings import Settings
from .mdb2fbx import Mdb2FbxConverter

MDB_2_FBX_BATCH_SETTINGS_TEMPLATE = {
    'exporter': mdb2fbx.MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE,
    'input': {
        'path': Directory,
        'exclude-files': {
            'starting-with': str,
            'ending-with': str,
            'containing': str
        },
        'include-files': {
            'starting-with': str,
            'ending-with': str,
            'containing': str
        }
    },
    'logging': {
        'level': str
    },
    'destination': {
        'root': Directory,
        'model': {
            'type': ['single-destination', 'by-prefix', 'folder-per-model'],
            'prefix-settings': dict,
            'destination': Directory
        },
        'animation': {
            'type': ['single-destination', 'by-prefix', 'with-model'],
            'prefix-settings': dict,
            'destination': Directory
        },
        'texture': {
            'type': ['single-destination', 'with-model'],
            'prefix-settings': dict,
            'destination': Directory
        }
    }
}

MDB_2_FBX_BATCH_DEFAULT_SETTINGS = {
    'exporter': mdb2fbx.MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS
}


class Mdb2FbxBatch:

    def __filter_collection_if_filter_exists__(self, property_name, filter_function, exclude = False):
        full_property_path = 'input.exclude-files.' + property_name if exclude else 'input.include-files.' + property_name
        if self.settings.has(full_property_path):
            self.collection = [resource for resource in self.collection if filter_function(
                resource, self.settings.get(full_property_path)
            )]

    def __init__(self, settings: Settings = Settings()):
        self.settings = settings

        resource_manager = ResourceManager(self.settings.get('input.path'))
        self.collection = resource_manager.get_all_of_type(ResourceTypes.MDB, ResourceTypes.MBA)

        FILTER_SPECIFICATION = {
            'starting-with': lambda resource, value: resource.file.name.startswith(value),
            'ending-with': lambda resource, value: resource.file.name.endswith(value),
            'containing': lambda resource, value: value in resource.file.name
        }

        if self.settings.has('input.include-files'):
            [self.__filter_collection_if_filter_exists__(a[0], a[1]) for a in FILTER_SPECIFICATION.items()]
        elif self.settings.has('input.exclude-files'):
            [self.__filter_collection_if_filter_exists__(a[0], a[1], True) for a in FILTER_SPECIFICATION.items()]

    def _find_in_collection_by_name_root_and_resource_type(self, name_root: str, resource_type: ResourceType):
        found_items = [resource for resource in self.collection if name_root == resource.file.name_root]
        found_items = [item for item in found_items if item.resource_type == resource_type]
        if len(found_items) == 0:
            return None
        else:
            return found_items[0]

    def _find_destination_folder(self, resource: Resource):

        destination_folder = None
        texture_destination_folder = None

        common_root = None
        if self.settings.has('destination.root'):
            common_root = self.settings.get('destination.root')

        def _consider_root(path):
            dir_ = None
            try:
                dir_ = Directory(path)
            except Exception as e:
                dir_ = common_root + path
            return dir_

        if resource.resource_type == ResourceTypes.MDB:

            # file destination
            model_destination_type = self.settings.get('destination.model.type')
            if model_destination_type == 'single-destination':
                destination_folder = self.settings.get('destination.model.destination')
            elif model_destination_type == 'by-prefix':
                destination_folder = \
                    _consider_root(
                        self.settings.get('destination.model.prefix-settings')[resource.file.name_prefix])
            else:
                raise Exception('destination type {} is not recognized'.format(model_destination_type))

            # texture files destination
            texture_destination_type = self.settings.get('destination.texture.type')
            if texture_destination_type == 'single-destination':
                texture_destination_folder = self.settings.get('destination.texture.destination')
            elif texture_destination_type == 'with-model':
                texture_destination_folder = destination_folder
            else:
                raise Exception('texture destination type {} is not recognized'.format(texture_destination_type))

        elif resource.resource_type == ResourceType.MBA:

            animation_destination_type = self.settings.get('destination.animation.type')
            if animation_destination_type == 'with-model':
                find_in_collection = self._find_in_collection_by_name_root_and_resource_type(resource.file.name_root,
                                                                                             ResourceTypes.MDB)
                if find_in_collection is not None:
                    destination_folder = self._find_destination_folder(find_in_collection)
                else:
                    raise Exception('no model found for animation {} to save with'.format(resource.file.name))
            elif animation_destination_type == 'single-destination':
                destination_folder = self.settings.get('destination.animation.destination')
            else:
                raise Exception(
                    'animation destination type {} is not recognized'.format(animation_destination_type))

        return destination_folder, texture_destination_folder

    def run(self):
        for resource in self.collection:
            converter = Mdb2FbxConverter(resource, self.settings.get('exporter'))
            destination_folder, texture_destination_folder = self._find_destination_folder(resource)
            converter.convert_and_export(destination_folder, texture_destination_folder)
