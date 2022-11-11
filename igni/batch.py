import resources
import mdb2fbx


class Batch:

    OUTPUT_ALREADY_EXISTS_REPLACE_HANDLING = 0
    OUTPUT_ALREADY_EXISTS_SKIP_HANDLING = 1
    OUTPUT_ALREADY_EXISTS_FAIL_HANDLING = 2

    TEXTURE_OUTPUT_HANDLING_WITH_MODEL = 0
    TEXTURE_OUTPUT_HANDLING_SEPARATE_FOLDER_FOR_ALL = 1

    def __init__(self):
        self.content_directory = ''
        self.destination_directory = ''
        self.resource_filter = None
        self.resolve_resource_output_path = None
        self.texture_output_handling = Batch.TEXTURE_OUTPUT_HANDLING_SEPARATE_FOLDER_FOR_ALL
        self.output_already_exists_handling = Batch.OUTPUT_ALREADY_EXISTS_REPLACE_HANDLING

    def content_directory(self, content_directory):
        self.content_directory = content_directory
        return self

    def destination_directory(self, destination_directory):
        self.destination_directory = destination_directory

    def resource_filter(self, resource_filter):
        self.resource_filter = resource_filter
        return self

    def resolve_resource_output_path(self, resolve_resource_output_path):
        self.resolve_resource_output_path = resolve_resource_output_path
        return self

    def texture_output_handling(self, texture_output_handling):
        self.texture_output_handling = texture_output_handling
        return self

    def output_already_exists_handling(self, output_already_exists_handling):
        self.output_already_exists_handling = output_already_exists_handling
        return self

    def run(self):
        pass