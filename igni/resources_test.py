from .resources import ResourceManager, ResourceTypes

resource_manager = ResourceManager("E:\\projects\\the_witcher\\content_pipeline\\unbiffed")

resource_manager.get_all_of_type(ResourceTypes.MDB)