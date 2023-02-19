from .mdb import Mdb
import os
import fbx
import sys
from .settings import Settings
from .resources import Directory, File, Resource, ResourceTypes
from .mdbutil import MdbWrapper, Material, Trimesh
from .logging_util import IgniLogger
from .meta_repository import EXPORT_METADATA_REPOSITORY

LOGGER = IgniLogger(__name__)

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

    """
    this class locates a texture by its name by means of searching specific folders in game contents
    """

    TEXTURE_EXTENSIONS = [
        'dds',
        'txi'
    ]

    def __init__(self, mdb2fbx_converter_reference):
        self.converter = mdb2fbx_converter_reference
        self.resource_location_directory = mdb2fbx_converter_reference.source.file.location
        self.logger = IgniLogger(TextureLocatorService.__name__)

    @classmethod
    def locate_texture(cls, directory: Directory, texture_name: str):
        for extension in cls.TEXTURE_EXTENSIONS:
            full_path = os.path.join(directory.full_path, texture_name + '.' + extension)
            if os.path.exists(full_path):
                return File(full_path)
        return None

    def locate(self, texture_name: str):  # TODO

        check_folders = [self.resource_location_directory] + \
                        [subdir for subdir in self.resource_location_directory.parent.subdirectories
                         if 'textures' in subdir.name] + \
                        [subdir for subdir in self.resource_location_directory.parent.subdirectories
                         if 'textures' not in subdir.name]

        for folder in check_folders:
            texture = self.locate_texture(folder, texture_name)
            if texture is not None:
                break

        if texture is None:
            self.logger.error('could not locate texture "{}"'.format(texture_name))
        else:
            self.logger.debug('located texture "{}"'.format(texture_name))

        return texture


class TextureConverterJob:

    """
    this class handles the logic of conversion of textures from arbitrary formats into arbitrary formats
    """

    def __init__(self, mdb2fbx_converter_reference):
        self.logger = IgniLogger(TextureConverterJob.__name__)

        if image is None:
            self.logger.error('could not create texture converter instance because wand is not properly installed')
            self.invalid = True
            return

        self.input_ = None
        self.target_location_: Directory = None
        self.target_fname_ = ''
        self.target_format_ = ''
        self.invalid = False

    def input(self, input_path):
        if isinstance(input_path, Resource):
            inp = input_path.file.full_path
        elif isinstance(input_path, File):
            inp = input_path.full_path

        try:
            self.input_ = image.Image(filename=inp)
        except Exception as e:
            self.logger.error('could not load input image "{}", error message: {}'.format(inp, e))
            self.invalid = True

        return self

    def target_dir(self, location: Directory):
        self.target_location_ = location
        return self

    def target_fname(self, fname):
        self.target_fname_ = fname
        return self

    def target_format(self, format_: str):
        self.target_format_ = format_
        return self

    def run(self):

        if self.input is None or self.target_location_ is None \
                or self.target_fname_ is None or len(self.target_fname_) == 0\
                or self.target_format_ is None or len(self.target_format_) == 0:
            self.logger.error("can't execute texture conversion job with incomplete description")
            self.invalid = True

        if self.invalid:
            return

        output_path = os.path.join(self.target_location_.full_path, self.target_fname_ + '.' + self.target_format_)

        try:
            self.input_.save(filename=output_path)
        except Exception as e:
            self.logger.error('could not write image: {}'.format(e))


class Mdb2FbxConverter:

    MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE = Settings({
        'texture-conversion': {
            'format': {'png', 'jpg', 'leave-as-is'}
        },
        'skip-nodes': {
            'if-name-contains': list,
            'of-type': list
        },
        'logging': IgniLogger.LOGGING_SETTINGS_TEMPLATE,
        'unit-conversion-factor': float,
        'flip-uvs': bool,
        'repository-path': str
    })

    MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS = Settings({
        'texture-conversion': {
            'format': 'png'
        },
        'skip-nodes': {
            'if-name-contains': ['shadow', 'Shadow']
        },
        'logging': IgniLogger.LOGGING_DEFAULT_SETTINGS,
        'unit-conversion-factor': 100.0,
        'flip-uvs': True
    })

    def __init__(self, source: Resource, settings: Settings = Settings()):
        assert (source.resource_type == ResourceTypes.MDB or source.resource_type == ResourceTypes.MBA)
        self.source: Resource = source

        self.settings: Settings = self.MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS
        if len(settings) > 0:
            self.settings.read_dict(settings).using_type_hint(self.MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE)

        self.texture_export_jobs = []

        self.context = None
        self.logger = IgniLogger(Mdb2FbxConverter.__name__, self.settings['logging'])

        self.texture_locator_service = TextureLocatorService(self)

        repository_path = self.settings.get('repository-path', default=None)
        EXPORT_METADATA_REPOSITORY.configure(repository_path, self.settings['logging'])

    def debug_log_trimesh(self, trimesh: Trimesh):

        nvert = len(trimesh.vertices)
        nfaces = len(trimesh.faces)
        nnorms = len(trimesh.normals)
        nbinorms = len(trimesh.binormals)
        ntangents = len(trimesh.tangents)

        self.logger.debug("mesh has {} vertices, {} faces, {} normals, {} binormals, {} tangents"
                          .format(nvert, nfaces, nnorms, nbinorms, ntangents))

        if nvert != nnorms:
            self.logger.warn("number of vertices not equal to number of normals in the mesh")

    def _export_material_textures_(self, mdb_material: Material):

        """
        material conversion being complex topic, this function represents a simplistic approach to texture conversion
        """

        if mdb_material is None:
            self.logger.debug('material is None, hence nothing to export and no fbx material created')
            return

        self.logger.debug("building fbx material from source material: {}".format(mdb_material))

        all_textures = mdb_material.textures
        all_textures.update(mdb_material.bumpmaps)

        for texture_type, texture_name in all_textures.items():

            # -- locate the texture
            texture_file = self.texture_locator_service.locate(texture_name)

            if texture_file is None and \
                    any([texture_name.endswith(channel_prefix) for channel_prefix in {'_r', '_g', '_b', '_a'}]): # probably pointer to a specific channel
                self.logger.info("'{}' probably points to a channel in another texture file".format(texture_name))
                texture_file = self.texture_locator_service.locate(texture_name[0:len(texture_name)-2])

            if texture_file is None:
                self.logger.error('texture with name "{}" not found'.format(texture_name))
                continue

            '''
            # --- link texture in the fbx material

            if texture_type in TEXTURE_MAPPING:
                texture = fbx.FbxFileTexture.Create(fbx_scene, texture_name)
                texture.SetFileName(texture_file.name + '.' + self.settings['texture-conversion']['format'])  # TODO this has to point to the exported file, also including relative positioning

                if texture_type in {'bumpmap', 'normalmap'}:
                    texture.SetTextureUse(fbx.FbxTexture.eBumpNormalMap)
                else:
                    texture.SetTextureUse(fbx.FbxTexture.eStandard)

                texture.SetMappingType(fbx.FbxTexture.eUV)
                texture.SetMaterialUse(fbx.FbxFileTexture.eModelMaterial)

                self.logger.debug('texture "{}" of type "{}" will be mapped to fbx material property "{}"'
                                  .format(texture_name, texture_type, TEXTURE_MAPPING[texture_type]))

                getattr(fbx_material, TEXTURE_MAPPING[texture_type]).ConnectSrcObject(texture)
            else:
                self.logger.warn('texture type "{}" will not be linked to fbx material as this texture type is not mapped'.format(texture_type))
            '''

            # -- add this texture to export jobs
            self.texture_export_jobs.append(TextureConverterJob(self).
                                            input(texture_file).
                                            target_fname(texture_name).
                                            target_format(self.settings['texture-conversion']['format']))

    def _build_fbx_mesh(self, fbx_mesh: fbx.FbxMesh, trimesh: Trimesh):

        # -- check input parameters
        self.debug_log_trimesh(trimesh)

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
                if self.settings['flip-uvs']:
                    coords = (uv_coord[0], 1 - uv_coord[1])
                else:
                    coords = (uv_coord[0], uv_coord[1])

                uv_element.GetDirectArray().Add(fbx.FbxVector2(coords[0], coords[1]))

    def _build_fbx_node(self, fbx_node: fbx.FbxNode, source_node: Mdb.Node, fbx_scene: fbx.FbxScene):

        self.logger.debug('start building fbx node')
        fbx_node.SetName(source_node.node_name.string)

        # do translation, rotation, etc.
        if source_node.node_type == Mdb.NodeType.trimesh or \
                source_node.node_type == Mdb.NodeType.skin:

            # --- geometry
            mesh = fbx.FbxMesh.Create(fbx_scene, '')
            fbx_node.AddNodeAttribute(mesh)
            self._build_fbx_mesh(mesh,
                                 Trimesh(source_node.node_data))

            # --- materials
            material = Material(source_node.node_data.material.data)
            EXPORT_METADATA_REPOSITORY.save_material_spec(
                self.source.file.name,
                source_node.node_name.string,
                material.as_dict())
            self._export_material_textures_(material)

        else:
            self.logger.debug('node type is not handled, it has been added to scene but its data wont be built')

    def _build_fbx_scene(self, fbx_scene: fbx.FbxScene, source: Mdb):

        def recursive_add_nodes(source_nodes, under_parent: fbx.FbxNode):
            for source_node in source_nodes:

                self.logger.context = {
                    'source_object': source_node,
                    'source_object_type': source_node.node_type.name,
                    'source_object_name': source_node.node_name.string
                }

                skip_containing_words = self.settings.get('skip-nodes.if-name-contains', default=[])

                if any([word in source_node.node_name.string for word in skip_containing_words]):
                    if len(source_node.children.data) > 0:
                        self.logger.warn('skipping node which contains children will result in data loss')
                    continue

                fbx_node = fbx.FbxNode.Create(fbx_scene, '')
                under_parent.AddChild(fbx_node)
                self._build_fbx_node(fbx_node, source_node, fbx_scene)

                self.logger.context = None

                recursive_add_nodes(
                    [child_ptr.data for child_ptr in source_node.children.data],
                    fbx_node
                )

        self.logger.debug('start building fbx scene from mdb scene tree')
        recursive_add_nodes([child_ptr.data for child_ptr in source.root_node.children.data],
                            fbx_scene.GetRootNode())

    def _export(self, scene: fbx.FbxScene, dest):

        self.logger.debug('exporting fbx scene')

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
        [job.target_dir(texture_destination).run() for job in self.texture_export_jobs]
        fbx_scene.Destroy()


if __name__ == '__main__':
    args = sys.argv

    src = Resource(File(args[1]))
    dest = Directory(args[2])
    texture_dest = Directory(args[3])
    settings = Settings()

    if len(args) > 4 and args[4].startswith('config='):
        # use yaml config
        path_to_yaml = args[4].split('=')[1]
        settings.read_yaml(path_to_yaml)
    elif len(args) > 4:
        settings.read_cmd_args(args[4:])

    Mdb2FbxConverter(src, settings).convert_and_export(dest, texture_dest)
