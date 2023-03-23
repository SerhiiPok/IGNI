import sys

import yaml

from .resources import Directory, ResourceType, ResourceManager, ResourceTypes, Resource
from .settings import Settings
from .mdb2fbx import FbxFileExportJob, Mdb2FbxConversionTaskDispatcher, TextureConverterJob, ResourceManagerTextureLocatorService
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from multiprocessing import Queue
from .logging_util import Configurer, DEFAULT_LOGGING_SETTINGS
import logging
from .app import PersistenceTask
from .meta_repository import EXPORT_METADATA_REPOSITORY

LOGGING_CONFIGURER = Configurer(DEFAULT_LOGGING_SETTINGS)
RESOURCE_MANAGER: ResourceManager = None
FEEDBACK_QUEUE: Queue = None

MDB_2_FBX_BATCH_SETTINGS_TEMPLATE = Settings({
    'exporter': FbxFileExportJob.MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE,
    'input': {
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
    'destination': {
        'model': {
            'destination': Directory,
            'organization': {'all-in-one-place', 'by-prefix', 'folder-per-model', 'custom'},
            'prefix-settings': dict,  # only if type is 'by-prefix'
            'custom': None
        },
        'animation': {
            'destination': Directory,  # required if 'single-destination' or 'by-prefix' are chosen
            'organization': {'all-in-one-place', 'by-prefix', 'with-model'},
            'prefix-settings': dict
        },
        'texture': {
            'destination': Directory,  # only required if organization is 'single-destination'
            'organization': {'all-in-one-place', 'with-model'},
            'prefix-settings': dict
        }
    }
})

MDB_2_FBX_BATCH_DEFAULT_SETTINGS = Settings({
    'exporter': FbxFileExportJob.MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS
})


class Mdb2FbxBatch:

    def __init__(self,
                 resource_manager: ResourceManager,
                 settings: Settings = Settings()):
        self.settings = settings
        self.collection = None
        self.logger = logging.getLogger(Mdb2FbxBatch.__name__)

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

            class ResourceNameFilterer:

                def __init__(self, lmbda, tokens):
                    self.lmbda = lmbda
                    self.tokens = tokens

                def __call__(self, resource):
                    return any([self.lmbda(resource.file.name, token) for token in self.tokens])

            for filter_spec in filters:
                filter_input_list = batch.settings.get(filter_spec[0], default=None)
                if filter_input_list is not None:
                    checks[filter_spec[1]].append(
                        ResourceNameFilterer(filter_spec[2], filter_input_list))

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

        if resource.resource_type == ResourceTypes.MDB:

            model_destination_settings: Settings = self.settings['destination']['model']
            texture_destination_settings: Settings = self.settings['destination']['texture']

            # --- resolve model destination folder
            model_destination: Directory = model_destination_settings['destination']
            model_organization = model_destination_settings.get('organization', default='all-in-one-place')

            if model_organization == 'all-in-one-place':
                destination_folder = model_destination
            elif model_organization == 'by-prefix':  # folder for this prefix under destination folder
                destination_folder = model_destination.create_subdirectory(
                    model_destination_settings['prefix-settings'].get(
                        resource.file.name_prefix if resource.file.name_prefix is not None else 'unassigned',
                        default='unassigned')
                )
            elif model_organization == 'folder-per-model':
                destination_folder = model_destination.create_subdirectory(resource.file.name)
            elif model_organization == 'custom':
                destination_folder = model_destination_settings['custom'](resource)
            else:
                raise Exception('this destination folder organization is not known')

            # --- resolve texture files destination folder
            texture_organization = texture_destination_settings['organization']

            if texture_organization == 'all-in-one-place':
                texture_destination_folder = texture_destination_settings['destination']
            elif texture_organization == 'with-model':
                texture_destination_folder = destination_folder
            else:
                raise Exception('this destination folder organization is not known')

        elif resource.resource_type == ResourceTypes.MBA:

            animation_destination_settings = self.settings['destination']['animation']

            animation_organization = animation_destination_settings['organization']

            if animation_organization == 'with-model':
                find_in_collection = self._find_in_collection_by_name_root_and_resource_type(resource.file.name_root,
                                                                                             ResourceTypes.MDB)
                if find_in_collection is not None:
                    destination_folder = self._find_destination_folder(find_in_collection)
                else:
                    raise Exception('no model found for animation {} to save with'.format(resource.file.name))
            elif animation_organization == 'by-prefix':
                destination_folder = animation_destination_settings['destination'].create_subdirectory(
                    animation_destination_settings['prefix-settings'].get(resource.file.name_prefix, 'unassigned')
                )
            elif animation_organization == 'all-in-one-place':
                destination_folder = animation_destination_settings['destination']
            else:
                raise Exception('this destination folder organization is not known')

        return destination_folder, texture_destination_folder

    def run(self):

        def handle_task_result(result):
            if result.exception() is not None:
                self.logger.error('EXCEPTION WHEN EXPORTING FBX: ' + str(result.exception()))
            if result.result() is not None:
                self.logger.error('type of the result is: ' + str(type(result.result())))
            if isinstance(result, Exception):
                self.logger.error('task execution finished with an exception: ' + str(result))

        handled_textures = set()
        task_dispatcher = Mdb2FbxConversionTaskDispatcher(ResourceManagerTextureLocatorService(RESOURCE_MANAGER),
                                                          RESOURCE_MANAGER,
                                                          FEEDBACK_QUEUE,
                                                          self.settings['exporter'])

        with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()-1) as task_pool:
            for resource in self.collection:
                destination_folder, texture_destination_folder = self._find_destination_folder(resource)
                tasks = task_dispatcher.get_tasks(resource, destination_folder, texture_destination_folder)

                for task in tasks:
                    if isinstance(task, TextureConverterJob):
                        if task.target_fname_ in handled_textures:
                            continue
                        else:
                            handled_textures.add(task.target_fname_)
                    task_pool.submit(task).add_done_callback(handle_task_result)


def feedback_handler_fn(feedback_queue: Queue, connection, logging_settings):
    logging.config.dictConfig(logging_settings)
    while True:
        if not feedback_queue.empty():
            feedback = feedback_queue.get()
            if isinstance(feedback, logging.LogRecord):
                logger = logging.getLogger(feedback.name)
                logger.handle(feedback)
            elif isinstance(feedback, PersistenceTask):
                feedback.data.to_sql(feedback.dest, connection)


if __name__ == '__main__':
    args = sys.argv
    config_path = args[1]

    with open(config_path, 'r') as stream:
        batch_input = yaml.safe_load(stream)

        if 'logging' in batch_input:
            logging.config.dictConfig(batch_input['logging'])

        # EXPORT_METADATA_REPOSITORY.configure(batch_input['repository-path'])

        FEEDBACK_QUEUE = multiprocessing.Manager().Queue(-1)
        RESOURCE_MANAGER = ResourceManager(batch_input['witcher-data'])
        feedback_handler = multiprocessing.Process(target=feedback_handler_fn,
                                                   args=(FEEDBACK_QUEUE,
                                                         EXPORT_METADATA_REPOSITORY.connection,
                                                         batch_input['logging']))
        feedback_handler.start()

        for batch_definition in batch_input['batch']:

            if batch_definition['type'] == 'mdb2fbx':
                Mdb2FbxBatch(RESOURCE_MANAGER,
                             Settings(batch_definition['settings']).using_type_hint(MDB_2_FBX_BATCH_SETTINGS_TEMPLATE)).run()
            else:
                raise Exception('unknown batch job type')

        while not FEEDBACK_QUEUE.empty():
            pass
        feedback_handler.kill()
