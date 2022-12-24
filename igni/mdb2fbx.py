from .mdb import Mdb
import os
import fbx
import sys
import logging
from .settings import Settings
from .resources import Directory, File, Resource, ResourceTypes
from .mdbutil import MdbWrapper, Material, Trimesh

LOGGER = logging.getLogger(__name__)

try:
    from wand import image
except Exception as e:
    LOGGER.error('could not import "image" from "wand", please, check wand installation, error message: {}'.format(str(e)))
    image = None

MEMORY_MANAGER = fbx.FbxManager.Create()


class OnModuleClose:

    def __del__(self):
        MEMORY_MANAGER.Destroy()


MODULE_CLOSE_INTERCEPTOR = OnModuleClose()


class TextureLocatorService:

    @classmethod
    def locate(cls, resource: Resource, texture_name: str):  # TODO
        loc_dir = resource.file.location

        candidates = [file for file in loc_dir.files if texture_name == file.name]

        # try searching texture folders under parent if nothing found else look in surroundings
        if len(candidates) == 0:
            first_priority_folders = [subdir for subdir in loc_dir.parent.subdirectories if 'textures' in subdir.name] # TODO parent
            second_priority_folders = [subdir for subdir in loc_dir.parent.subdirectories if 'textures' not in subdir.name]

        for folder in first_priority_folders + second_priority_folders:
            candidates = [file for file in folder.files if texture_name == file.name]
            if len(candidates) == 0:
                break

        # TODO log properly
        if len(candidates) == 0:
            return None
        elif len(candidates) == 1:
            return candidates[0]
        elif len(candidates) > 1:
            logging.getLogger(cls.__name__).warning('located multiple textures with name "{}", choosing first'.format(texture_name))
            return candidates[0]


class TextureConverter:

    def __init__(self, inp):
        self.logger = logging.getLogger(type(self).__name__)

        if image is None:
            self.logger.debug('could not create texture converter instance because "wand" dependency could not be imported.')
            self.invalid = True
            return

        if isinstance(inp, Resource):
            inp = inp.file.full_path
        elif isinstance(inp, File):
            inp = inp.full_path

        try:
            self.input = image.Image(filename=inp)
        except Exception as e:
            self.logger.debug('could not load input image "{}", error message: {}'.format(inp, e))
            self.invalid = True

        self.location: Directory = None
        self.filename = ''
        self.format = ''

    def under(self, location: Directory):
        self.location = location
        return self

    def fname(self, fname):
        self.filename = fname
        return self

    def convert(self, format):
        output_path = os.path.join(self.location.full_path, self.filename + '.' + format)
        try:
            self.input.save(filename=output_path)
        except Exception as e:
            self.logger.error('could not write image: {}'.format(e))

        try:
            return File(output_path)
        except Exception as e:
            self.logger.error('texture was not written: {}'.format(e))


class Mdb2FbxConverterLogger:

    def __init__(self, input_file: File):
        self.logger = logging.getLogger(Mdb2FbxConverter.__name__)
        self.input_file = input_file
        self.context_ = None

    def context(self, context):
        self.context_ = context
        return self

    def _get_context_inf(self):
        if isinstance(self.context_, Mdb.Node):
            return self.context_.node_name.string
        else:
            return ''

    # logging at four levels
    def _decorate_message(self, msg):
        inf = {
            'input': str(self.input_file),
            'msg': msg
        }  # TODO file must have full file path attribute

        if self.context_ is not None:
            inf['context'] = {
                'type': str(type(self.context_)),
                'info': self._get_context_inf()
            }

        return str(inf)

    def debug(self, msg):
        self.logger.debug(self._decorate_message(msg))

    def info(self, msg):
        self.logger.info(self._decorate_message(msg))

    def warn(self, msg):
        self.logger.warning(self._decorate_message(msg))

    def error(self, msg):
        self.logger.error(self._decorate_message(msg))

    def log_trimesh(self, trimesh: Trimesh):

        if len(trimesh.vertices) == 0:
            self.warn('mesh vertices array is empty')
            return

        if len(trimesh.faces) == 0:
            self.warn('mesh faces are not defined')
        if len(trimesh.normals) == 0:
            self.warn('mesh normals are not defined')
        # TODO uvs

        inconsistent_lengths = len(trimesh.vertices) != len(trimesh.normals)
        for uv_set in trimesh.uv_sets:
            if len(trimesh.vertices) != len(uv_set):
                inconsistent_lengths = True
        if inconsistent_lengths:
            self.warn('number of mesh vertices is not equal to number of normals or uvs')

        self.debug('mesh has {} faces and {} vertices'.format(
            len(trimesh.faces), len(trimesh.vertices)))


class Mdb2FbxConverter:

    MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE = Settings({
        'texture-conversion': {
            'format': {'png', 'jpg', 'leave-as-is'}
        },
        'skip-nodes': {
            'if-name-contains': list,
            'of-type': list
        },
        'logging': {
            'level': {'DEBUG', 'INFO', 'WARN', 'ERROR'}
        },
        'unit-conversion-factor': float
    })

    MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS = Settings({
        'texture-conversion': {
            'format': 'png'
        },
        'skip-nodes': {
            'if-name-contains': []
        },
        'logging': {
            'level': 'INFO'
        },
        'unit-conversion-factor': 100.0
    })

    def __init__(self, source: Resource, settings: Settings = Settings()):
        assert (source.resource_type == ResourceTypes.MDB or source.resource_type == ResourceTypes.MBA)
        self.source: Resource = source

        self.settings: Settings = self.MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS
        if len(settings) > 0:
            self.settings.read_dict(settings)

        self.texture_export_jobs = []

        self.context = None
        self.mdb2fbx_logger = Mdb2FbxConverterLogger(self.source.file)
        self.mdb2fbx_logger.logger.setLevel(self.settings['logging']['level'])

    def _build_fbx_material(self, fbx_material: fbx.FbxSurfacePhong, mdb_material: Material):
        # for the moment, simply export textures, logic will come later
        self.mdb2fbx_logger.warn('only texture files will be exported when writing materials, converting to fbx materials not yet implemented')

        for texture in list(mdb_material.textures.values()) + list(mdb_material.bumpmaps.values()):
            file = TextureLocatorService.locate(self.source, texture)
            if file is not None:
                self.texture_export_jobs.append(TextureConverter(file).fname(texture))

    def _build_fbx_mesh(self, fbx_mesh: fbx.FbxMesh, trimesh: Trimesh):

        # -- check input parameters
        self.mdb2fbx_logger.log_trimesh(trimesh)

        # -- build mesh data
        fbx_mesh.InitControlPoints(len(trimesh.vertices))
        unit_conversion_factor = self.settings['unit-conversion-factor']
        for i in range(0, len(trimesh.vertices)):
            vertex = trimesh.vertices[i]
            fbx_mesh.SetControlPointAt(
                fbx.FbxVector4(vertex[0] * unit_conversion_factor,
                               vertex[1] * unit_conversion_factor,
                               vertex[2] * unit_conversion_factor, 0.0),
                i
            )

        for i in range(len(trimesh.faces)):
            face = trimesh.faces[i]
            fbx_mesh.BeginPolygon()
            for vertex_index in face:
                fbx_mesh.AddPolygon(vertex_index)
            fbx_mesh.EndPolygon()

        for uv_set_name in trimesh.uv_sets:
            uv_element: fbx.FbxLayerElementUV = fbx_mesh.CreateElementUV(uv_set_name)
            uv_element.SetMappingMode(fbx.FbxLayerElementUV.eByControlPoint)
            uv_element.SetReferenceMode(fbx.FbxLayerElement.eDirect)

            for uv_coord in trimesh.uv_sets[uv_set_name]:
                uv_element.GetDirectArray().Add(fbx.FbxVector2(uv_coord[0], uv_coord[1]))

    def _build_fbx_node(self, fbx_node: fbx.FbxNode, source_node: Mdb.Node, fbx_scene: fbx.FbxScene):

        fbx_node.SetName(source_node.node_name.string)

        self.mdb2fbx_logger.debug('node type is {}'.format(source_node.node_type.name))

        # do translation, rotation, etc.
        if source_node.node_type == Mdb.NodeType.trimesh or \
                source_node.node_type == Mdb.NodeType.skin:
            mesh = fbx.FbxMesh.Create(fbx_scene, '')
            fbx_node.AddNodeAttribute(mesh)
            self._build_fbx_mesh(mesh,
                                 Trimesh(source_node.node_data))
        else:
            self.mdb2fbx_logger.debug('this node type is not handled')

    def _build_fbx_scene(self, fbx_scene: fbx.FbxScene, source: Mdb):

        self.mdb2fbx_logger.debug('start building fbx scene')

        def recursive_add_nodes(source_nodes, under_parent: fbx.FbxNode):
            for source_node in source_nodes:

                self.mdb2fbx_logger.context(source_node)

                skip_containing_words = self.settings.get('skip-nodes.if-name-contains', default=[])

                if any([word in source_node.node_name.string for word in skip_containing_words]):
                    if len(source_node.children.data) > 0:
                        self.mdb2fbx_logger.warn(
                            'skipping node {} which contains children will result in data loss'.
                                format(source_node.node_name.string)
                        )
                    continue

                fbx_node = fbx.FbxNode.Create(fbx_scene, '')
                under_parent.AddChild(fbx_node)
                self._build_fbx_node(fbx_node, source_node, fbx_scene)

                self.mdb2fbx_logger.context(None)

                recursive_add_nodes(
                    [child_ptr.data for child_ptr in source_node.children.data],
                    fbx_node
                )

        self.mdb2fbx_logger.debug('building node tree')
        recursive_add_nodes([child_ptr.data for child_ptr in source.root_node.children.data],
                            fbx_scene.GetRootNode())

    def _export(self, scene: fbx.FbxScene, dest):

        self.mdb2fbx_logger.debug('exporting fbx scene')

        fbx_exporter = fbx.FbxExporter.Create(MEMORY_MANAGER, '')
        fbx_exporter.Initialize(os.path.join(dest, self.source.file.name), -1, MEMORY_MANAGER.GetIOSettings())
        fbx_exporter.Export(scene)
        fbx_exporter.Destroy()

    def convert(self) -> fbx.FbxScene:
        mdb_source = Mdb.from_file(str(self.source.file))  # TODO add full file path
        dest_scene = fbx.FbxScene.Create(MEMORY_MANAGER, mdb_source.root_node.node_name.string)
        self._build_fbx_scene(dest_scene, mdb_source)
        return dest_scene

    def convert_and_export(self, destination: Directory, texture_destination: Directory):
        fbx_scene = self.convert()
        self._export(fbx_scene, destination.full_path)
        [job.under(texture_destination).convert(self.settings['texture-conversion']['format']) for job in self.texture_export_jobs]
        fbx_scene.Destroy()


if __name__ == '__main__':
    args = sys.argv

    src = Resource(File(args[1]))
    dest = Directory(args[2])
    settings = Settings()

    if len(args) > 3 and args[3].startswith('config='):
        # use yaml config
        path_to_yaml = args[3].split('=')[1]
        settings.read_yaml(path_to_yaml)
    elif len(args) > 3:
        settings.read_cmd_args(args[3:])

    Mdb2FbxConverter(src, settings).convert_and_export(dest)
