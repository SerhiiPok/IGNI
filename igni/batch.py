import sys
import mdb2fbx
from .resources import Directory, ResourceType, ResourceManager, ResourceTypes, Resource
from .settings import Settings
from .mdb2fbx import Mdb2FbxConverter

MDB_2_FBX_BATCH_SETTINGS_TEMPLATE = Settings({
    'exporter': mdb2fbx.MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE,
    'input': {
        'path': Directory,
        'exclude-files': {
            'starting-with': list,
            'ending-with': list,
            'containing': list
        },
        'include-files': {
            'starting-with': list,
            'ending-with': list,
            'containing': list
        }
    },
    'logging': {
        'level': str
    },
    'destination': {
        'model': {
            'destination': Directory,
            'organization': {'all-in-one-place', 'by-prefix', 'folder-per-model', 'custom'},
            'prefix-settings': dict  # only if type is 'by-prefix'
        },
        'animation': {
            'destination': Directory,  # required if 'single-destination' or 'by-prefix' are chosen
            'organization': {'all-in-one-place', 'by-prefix', 'with-model'},
            'prefix-settings': dict
        },
        'texture': {
            'destination': Directory,  # only required if organization is 'single-destination'
            'organization': {'single-destination', 'with-model'},
            'prefix-settings': dict
        }
    }
})

MDB_2_FBX_BATCH_DEFAULT_SETTINGS = Settings({
    'exporter': mdb2fbx.MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS
})


class Mdb2FbxBatch:

    def __init__(self, settings: Settings = Settings()):
        self.settings = settings

        resource_manager = ResourceManager(self.settings['input']['path'])

        def get_item_filter(batch):

            checks = {'positive': [], 'negative': []}

            filters = [
                ('input.exclude-files.starting-with', 'negative', lambda x, y: x.startswith(y)),
                ('input.exclude-files.ending-with', 'negative', lambda x, y: x.endswith(y)),
                ('input.exclude-files.containing', 'negative', lambda x, y: y in x),
                ('input.include-files.starting-with', 'positive', lambda x, y: x.startswith(y)),
                ('input.include-files.ending-with', 'positive', lambda x, y: x.endswith(y)),
                ('input.include-files.containing', 'positive', lambda x, y: y in x)
            ]

            for filter_spec in filters:
                filter_input_list = batch.settings.get(filter_spec[0], None)
                if filter_input_list is not None:
                    checks[filter_spec[1]].append(
                        lambda rsrc: any([filter_spec[2](rsrc.file.name, word) for word in filter_input_list]))

            def do_filter(resource):
                if not all([check(resource) for check in checks['positive']]):
                    return False

                if any([check(resource) for check in checks['negative']]):
                    return False

                return True

            return do_filter

        self.collection = resource_manager.get_all_of_type((ResourceTypes.MDB, ResourceTypes.MBA), get_item_filter(self))

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
            converter = Mdb2FbxConverter(resource, self.settings['exporter'])
            destination_folder, texture_destination_folder = self._find_destination_folder(resource)
            converter.convert_and_export(destination_folder)  # TODO implement texture destination folder


if __name__ == '__main__':
    args = sys.argv
    batch_name = args[1]
    config_path = args[2]

    if batch_name == 'mdb2fbx':
        Mdb2FbxBatch(Settings.read_yaml(config_path)).run()
    else:
        raise Exception('batch name "{}" is unknown'.format(batch_name))
