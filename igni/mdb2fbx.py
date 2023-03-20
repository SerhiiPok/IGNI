from .mdb import Mdb
import os
import fbx
import sys
from .settings import Settings
from .resources import Directory, File, Resource, ResourceTypes
from .mdbutil import MdbWrapper, Material, Trimesh, NodeProperties
from .logging_util import IgniLogger
from .meta_repository import EXPORT_METADATA_REPOSITORY
from .task_execution import AsyncTaskExecutor
from squaternion import Quaternion
from scipy.spatial.transform import Rotation

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


# annotation
def picklable(fun):
    return fun


class CoordinateSystemService:

    COORDINATE_SYSTEM_SETTINGS_DEFAULT_SETTINGS = Settings({
        'source-unit': 'm',
        'target-unit': 'cm',
        'coordinate-system-mapping': {
            'x': 'y',
            'y': 'z',
            'z': 'x'
        }
    })

    COORDINATE_SYSTEM_SETTINGS_TEMPLATE = Settings({
        'source-unit': {'m', 'cm'},
        'target-unit': {'m', 'cm'},
        'coordinate-system-mapping': {
            'x': {'y', '-y', 'x', '-x', 'z', '-z'},
            'y': {'y', '-y', 'x', '-x', 'z', '-z'},
            'z': {'y', '-y', 'x', '-x', 'z', '-z'}
        }
    })

    MEASUREMENT_UNIT_TO_CM = {
        'm': 100.0,
        'cm': 1.0
    }

    def __init__(self, settings: Settings = Settings()):
        self.settings = self.COORDINATE_SYSTEM_SETTINGS_DEFAULT_SETTINGS
        self.settings.read_dict(settings).using_type_hint(self.COORDINATE_SYSTEM_SETTINGS_TEMPLATE)

        self.multiplication_factor = self.MEASUREMENT_UNIT_TO_CM[self.settings['source-unit']] / \
                                     self.MEASUREMENT_UNIT_TO_CM[self.settings['target-unit']]

        self.coord_mapping = [(0, 1.0), (1, 1.0),
                              (2, 1.0)]  # meaning: for zeroth index take zeroth member of input and multiply by 1.0
        self.coord_names = {'x': 0, 'y': 1, 'z': 2}

        for from_axis, to_axis in self.settings['coordinate-system-mapping'].items():
            negation_factor = 1.0
            if to_axis.startswith('-'):
                negation_factor = -1.0
            self.coord_mapping[self.coord_names[from_axis]] = (
                self.coord_names[to_axis.replace('-', '')], negation_factor)

    def location(self, vector_xyz):
        if len(vector_xyz) != 3:
            raise Exception('illegal argument {} supplied'.format(vector_xyz))
        return (vector_xyz[self.coord_mapping[0][0]] * self.coord_mapping[0][1] * self.multiplication_factor,
                vector_xyz[self.coord_mapping[1][0]] * self.coord_mapping[1][1] * self.multiplication_factor,
                vector_xyz[self.coord_mapping[2][0]] * self.coord_mapping[2][1] * self.multiplication_factor)

    def rotation(self, vector_xyz):
        if len(vector_xyz) != 3:
            raise Exception('illegal argument {} supplied'.format(vector_xyz))
        return (vector_xyz[self.coord_mapping[0][0]],
                vector_xyz[self.coord_mapping[1][0]],
                vector_xyz[self.coord_mapping[2][0]])

    def __str__(self):
        return str(self.coord_mapping)


class TextureLocatorService:

    """
    this class locates a texture by its name by means of searching specific folders in game contents
    """

    TEXTURE_EXTENSIONS = [
        'dds',
        'txi'
    ]

    def __init__(self, mdb_location: Directory):
        self.resource_location_directory = mdb_location

    @classmethod
    def locate_texture(cls, directory: Directory, texture_name: str):
        for extension in cls.TEXTURE_EXTENSIONS:
            paths_to_check = [
                os.path.join(directory.full_path, texture_name + '.' + extension),
                os.path.join(directory.full_path, texture_name.lower() + '.' + extension)  # also check lower case
            ]

            for path in paths_to_check:
                if os.path.exists(path):
                    return File(path)
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

        return texture


@picklable
class TextureConversionResult:

    def __init__(self, converted_texture_path: str):

        self.converted_texture_file = None

        try:
            self.converted_texture_file = File(converted_texture_path)
        except Exception:
            pass

    def successful(self):
        return self.converted_texture_file is not None


@picklable
class TextureConverterJob:

    """
    this class handles the logic of conversion of textures from arbitrary formats into arbitrary formats
    """

    def __init__(self, mdb2fbx_converter_reference):
        # self.logger = IgniLogger(TextureConverterJob.__name__)

        if image is None:
            # self.logger.error('could not create texture converter instance because wand is not properly installed')
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
        self.input_ = inp
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

    def __call__(self):
        self.run()

    def run(self):

        if self.input is None or self.target_location_ is None \
                or self.target_fname_ is None or len(self.target_fname_) == 0\
                or self.target_format_ is None or len(self.target_format_) == 0:
            # self.logger.error("can't execute texture conversion job with incomplete description")
            self.invalid = True

        if self.invalid:
            return

        try:
            self.input_ = image.Image(filename=self.input_)
        except Exception as e:
            # self.logger.error('could not load input image "{}", error message: {}'.format(inp, e))
            self.invalid = True

        output_path = os.path.join(self.target_location_.full_path, self.target_fname_ + '.' + self.target_format_)

        # only if not already exists...
        if not File.exists(output_path):
            try:
                self.input_.save(filename=output_path)
            except Exception:
                # self.logger.error('could not write image: {}'.format(e))
                pass

        return TextureConversionResult(output_path)


@picklable
class FbxFileExportJob:

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
        'repository-path': str,
        'coordinate-system': CoordinateSystemService.COORDINATE_SYSTEM_SETTINGS_TEMPLATE
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
        'flip-uvs': True,
        'coordinate-system': CoordinateSystemService.COORDINATE_SYSTEM_SETTINGS_DEFAULT_SETTINGS
    })

    def __init__(self,
                 source: Resource,
                 destination: Directory,  # can be None if no export intended
                 texture_destination: Directory,  # can be None if no export intended
                 settings: Settings = Settings()):
        assert (source.resource_type == ResourceTypes.MDB or source.resource_type == ResourceTypes.MBA)

        self.source: Resource = source
        self.output_destination: Directory = destination
        self.texture_output_destination: Directory = texture_destination
        self.settings: Settings = self.MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS.read_dict(settings).using_type_hint(self.MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE)
        self.texture_export_jobs = []
        self.context = None
        self._logger = None
        self.file_meta = {
            'file': self.source.file.name,
            'node_count': 0,
            'mesh_count': 0,
            'material_count': 0,
            'bone_count': 0,
            'animation_count': 0,
            'tri_count': 0
        }
        self.coord_service = CoordinateSystemService(self.settings['coordinate-system'])

    @property
    def logger(self):
        if self._logger is not None:
            return self._logger

        self._logger = IgniLogger(FbxFileExportJob.__name__, self.settings['logging'])
        return self._logger

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

    def _quaternion_to_euler_and_log_(self, quat: tuple):

        rotation = Rotation.from_quat(quat)
        self.logger.debug('converting from input quaternion {}'.format(quat))

        rotation = rotation.as_euler('yzx', degrees=True)
        self.logger.debug('converted to euler: {}'.format(rotation.tolist()))

        return rotation.tolist()

    def _build_fbx_mesh(self, fbx_mesh: fbx.FbxMesh, trimesh: Trimesh):

        self.file_meta['mesh_count'] += 1
        self.file_meta['tri_count'] += len(trimesh.faces)

        # -- check input parameters
        self.debug_log_trimesh(trimesh)

        # -- build mesh data
        fbx_mesh.InitControlPoints(len(trimesh.vertices))
        for i in range(0, len(trimesh.vertices)):
            vertex = self.coord_service.location(trimesh.vertices[i])
            fbx_mesh.SetControlPointAt(fbx.FbxVector4(vertex[0], vertex[1], vertex[2], 0.0), i)

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

    def _transfer_node_properties_(self, fbx_node: fbx.FbxNode, node_properties: NodeProperties):

        if node_properties is None:
            self.logger.warn('received empty node properties')
            return

        if node_properties.location is not None and (not node_properties.location.empty()):
            location = self.coord_service.location(node_properties.location.value)
            self.logger.debug('setting node location to {}'.format(location))
            fbx_node.LclTranslation.Set(fbx.FbxDouble3(location[0],
                                                       location[1],
                                                       location[2]))

        if node_properties.rotation is not None and (not node_properties.rotation.empty()):
            rotation = self._quaternion_to_euler_and_log_(node_properties.rotation.value)
            fbx_node.LclRotation.Set(fbx.FbxDouble3(rotation[0],
                                                    rotation[1],
                                                    rotation[2]))
            self.logger.debug('set node euler rotation to {}'.format(list(fbx_node.LclRotation.Get())))

    def _build_fbx_node(self, fbx_node: fbx.FbxNode, source_node: Mdb.Node, fbx_scene: fbx.FbxScene):

        """
        EXPORT_METADATA_REPOSITORY.save_mdb_node_meta(
            self.source.file.name,
            source_node.node_name.string,
            source_node.node_type.name)
        """
        self.file_meta['node_count'] += 1

        self.logger.debug('start building fbx node')
        fbx_node.SetName(source_node.node_name.string)

        node_properties = None
        try:
            node_properties = NodeProperties(source_node.controller_defs.data, source_node.controller_data.data)
        except Exception as e:
            self.logger.error('could not read node properties: {}'.format(e))
        self._transfer_node_properties_(fbx_node, node_properties)

        if source_node.node_type == Mdb.NodeType.trimesh or \
                source_node.node_type == Mdb.NodeType.skin:

            # --- geometry
            mesh = fbx.FbxMesh.Create(fbx_scene, '')
            fbx_node.AddNodeAttribute(mesh)
            self._build_fbx_mesh(mesh,
                                 Trimesh(source_node.node_data))

            # --- materials
            material = None
            try:
                material = Material.from_node(source_node)
                if not material.is_empty():
                    self.file_meta['material_count'] += 1
            except Exception as e:
                self.logger.error("exception while parsing material: {}".format(e))

            """
            EXPORT_METADATA_REPOSITORY.save_material_spec(
                self.source.file.name,
                source_node.node_name.string,
                material.as_dict())
            """

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

        """
        EXPORT_METADATA_REPOSITORY.save_mdb_file_meta(self.file_meta['file'],
                                                      self.file_meta['node_count'],
                                                      self.file_meta['mesh_count'],
                                                      self.file_meta['material_count'],
                                                      self.file_meta['bone_count'],
                                                      self.file_meta['animation_count'],
                                                      self.file_meta['tri_count'])
        """

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

    def convert_and_export(self):

        fbx_scene = self.convert()
        self._export(fbx_scene, self.output_destination.full_path)
        fbx_scene.Destroy()

    def __call__(self):
        self.convert_and_export()


class Mdb2FbxConversionTaskDispatcher:

    """
    because converting mdb to fbx is a complex process involving generation of textures, generation of fbx
    etc., it can be broken down into tasks which then can also be executed with parallelism
    this class creates such tasks
    """

    def __init__(self,
                 source: Resource,
                 destination: Directory,
                 texture_destination: Directory,
                 settings: Settings = Settings()):

        self.source = source
        # TODO settings system is chaotic
        self.settings = FbxFileExportJob.MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS.read_dict(settings).using_type_hint(FbxFileExportJob.MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE)
        self.destination = destination
        self.texture_destination = texture_destination
        self.logger = IgniLogger(Mdb2FbxConversionTaskDispatcher.__name__, settings['logging']) # TODO logging settings do not make any sense

    def get_tasks(self):
        """
        :return: a list of tasks that should be executed to convert an mdb to an fbx
        """

        tasks = []

        wrapper = MdbWrapper(self.source.get())

        # export fbx file
        tasks.append(FbxFileExportJob(self.source, self.destination, self.texture_destination, self.settings))

        # export textures
        texture_locator_service = TextureLocatorService(self.source.file.location)
        for material in wrapper.materials:
            for texture_name in material.get_all_texture_names():
                texture_file = texture_locator_service.locate(texture_name)

                if texture_file is None and \
                        any([texture_name.endswith(channel_prefix) for channel_prefix in
                             {'_r', '_g', '_b', '_a'}]):  # probably pointer to a specific channel
                    self.logger.info('{} probably points to a channel in a texture file'.format(texture_name))
                    texture_file = texture_locator_service.locate(texture_name[0:len(texture_name) - 2])

                if texture_file is None:
                    self.logger.context = {'file': self.source.file.full_file_name}
                    self.logger.error('could not locate texture with name "{}"'.format(texture_name))
                    continue
                else:
                    self.logger.info('located texture {}'.format(texture_name))

                tasks.append(
                    TextureConverterJob(self).
                        input(texture_file).
                        target_fname(texture_name).
                        target_format(self.settings['texture-conversion']['format']).
                        target_dir(self.texture_destination)
                )

        return tasks


def mdb_to_fbx(source: Resource,
               destination: Directory,
               texture_destination: Directory,
               settings: Settings = Settings()):
    [task() for task in Mdb2FbxConversionTaskDispatcher(source,
                                                        destination,
                                                        texture_destination,
                                                        settings).get_tasks()]  # everything needs to be runnable and picklable


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

    mdb_to_fbx(src, dest, texture_dest, settings)
