from mdb import Mdb
import fbx
import sys
import logging
from settings import Settings
from resources import Directory, Resource, ResourceTypes

MEMORY_MANAGER = fbx.FbxManager.Create()


class OnModuleClose:

    def __del__(self):
        print('on module close called')
        MEMORY_MANAGER.Destroy()


MODULE_CLOSE_INTERCEPTOR = OnModuleClose()


LOGGER = logging.getLogger(__name__)


# a wrapper class for trimesh (triangular mesh) objects
class Trimesh:

    def __init__(self, source_node: Mdb.Node):
        if source_node is None:
            raise Exception('tried to create a trimesh wrapper but source node is None')
        if source_node.node_type not in (Mdb.NodeType.trimesh, Mdb.NodeType.skin):
            raise Exception('cannot create a trimesh wrapper from a node that is not skin or trimesh')

        self.vertices = []
        self.faces = []
        self.normals = []
        self.uv_sets = {}

        self.set_data(source_node)

    def set_data(self, source_node: Mdb.Node):
        node_data = source_node.node_data
        self.vertices = [[v.x, v.y, v.z] for v in node_data.vertices.data]
        self.faces = [[f.vert1, f.vert2, f.vert3] for f in node_data.faces.data]
        self.normals = [[n.x, n.y, n.z] for n in node_data.normals.data]

        for i in range(0, 4):
            uv_array_pointer = node_data.uvs[i]
            if uv_array_pointer.data is not None and len(uv_array_pointer.data) > 0:
                self.uvs_sets['UvSet{}'.format(i)] = [[c.u, c.v] for c in uv_array_pointer.data]


# a wrapper class for mdb materials
class Material:

    def __init__(self, material_descr: Mdb.Material):
        if material_descr is None:
            raise Exception('tried to create material wrapper but material description is None')

        self.shader = ''
        self.textures = {}

        self.set_data(material_descr)

    def set_data(self, material_descr: Mdb.Material):

        for line in material_descr.material_spec:
            if line.startswith('shader'):
                self.shader = line.replace('shader', '').lstrip().rstrip()
            else:
                texture_spec = line.split(' ')
                if len(texture_spec) == 1:
                    raise Exception('found unusual material specification line: ' + line)
                else:
                    self.textures[' '.join(texture_spec[:(len(texture_spec)-1)])] = texture_spec[len(texture_spec)-1]


class Mdb2FbxConverter:

    def _get_context_inf(self):
        if isinstance(self.context, Mdb.Node):
            return self.context.node_name
        else:
            return ''

    # logging at four levels
    def _decorate_message(self, msg):
        inf = {
            'input': self.source.file.full_file_name,
            'msg': msg
        }  # TODO file must have full file path attribute

        if self.context is not None:
            inf['context'] = {
                'type': str(type(self.context)),
                'info': self._get_context_inf(self.context)
            }

        return str(inf)

    def debug(self, msg):
        LOGGER.debug(self._decorate_message(msg))

    def info(self, msg):
        LOGGER.info(self._decorate_message(msg))

    def warn(self, msg):
        LOGGER.warning(self._decorate_message(msg))

    def error(self, msg):
        LOGGER.error(self._decorate_message(msg))

    def _init_settings(self, settings: Settings):
        self.settings \
            .set('texture-handling.method', settings.get('texture-handling.method', 'with-fbx')) \
            .set('skip-shadowbones', settings.get('skip-shadowbones', True)) \
            .set('logging.level', settings.get('logging.level', logging.WARNING))

        if settings.get('texture-handling.method') == 'dest-dir':
            self.settings.set('texture-handling.dest-dir', settings.get('texture-handling.dest-dir'))

    def __init__(self, source: Resource, settings: Settings = Settings()):
        assert(source.resource_type == ResourceTypes.MDB or source.resource_type == ResourceTypes.MBA)
        self.source: Resource = source
        self.settings: Settings = Settings()
        self.context = None

        self._init_settings(settings)

    def _log_trimesh(self, trimesh: Trimesh):

        if len(trimesh.vertices) == 0:
            self.warn('mesh vertices array is empty')
            return

        if len(trimesh.faces) == 0:
            self.warn('mesh faces are not defined')
        if len(trimesh.normals) == 0:
            self.warn('mesh normals are not defined')
        # TODO uvs

        if len(trimesh.vertices) != len(trimesh.normals) or len(trimesh.vertices) != len(trimesh.uvs):
            self.warn('number of mesh vertices is not equal to number of normals or uvs')

        self.debug('mesh has {} faces and {} vertices'.format(
            len(trimesh.faces), len(trimesh.vertices)))

    def _build_fbx_mesh(self, fbx_mesh: fbx.FbxMesh, trimesh: Trimesh):

        # -- check input parameters
        self._log_trimesh(trimesh)

        # -- build mesh data
        fbx_mesh.InitControlPoints(len(trimesh.vertices))
        for i in range(0, len(trimesh.vertices)):
            vertex = trimesh.vertices[i]
            fbx_mesh.SetControlPointAt(
                fbx.FbxVector4(vertex[0], vertex[1], vertex[2], 0.0),
                i
            )

        for i in range(len(trimesh.faces)):
            face = trimesh.faces[i]
            fbx_mesh.BeginPolygon()
            for vertex_index in face:
                fbx_mesh.AddPolygon(vertex_index)
            fbx_mesh.EndPolygon()

        for uv_set in trimesh.uvs:
            uv_element: fbx.FbxLayerElementUV = fbx_mesh.CreateElementUV(uv_set)
            uv_element.SetMappingMode(fbx.FbxLayerElementUV.eByControlPoint)
            uv_element.SetReferenceMode(fbx.FbxLayerElement.eDirect)

            for uv_coord in trimesh.uvs[uv_set]:
                uv_element.GetDirectArray().Add(fbx.FbxVector2(uv_coord[0], uv_coord[1]))

    def _build_fbx_node(self, fbx_node: fbx.FbxNode, source_node: Mdb.Node, fbx_scene: fbx.FbxScene):

        fbx_node.SetName(source_node.node_name.string)

        self.debug('node type is {}'.format(source_node.node_type.name))

        # do translation, rotation, etc.
        if source_node.node_type == Mdb.NodeType.trimesh or \
                source_node.node_type == Mdb.NodeType.skin:
            mesh = fbx.FbxMesh.Create(fbx_scene, '')
            fbx_node.AddNodeAttribute(mesh)
            self._build_fbx_mesh(mesh,
                                 Trimesh(source_node))
        else:
            self.debug('this node type is not handled')

    def _build_fbx_scene(self, fbx_scene: fbx.FbxScene, source: Mdb):

        self.debug('start building fbx scene')

        def recursive_add_nodes(source_nodes, under_parent: fbx.FbxNode):
            for source_node in source_nodes:

                self.context = source_node

                fbx_node = fbx.FbxNode.Create(fbx_scene, '')
                under_parent.AddChild(fbx_node)
                self._build_fbx_node(fbx_node, source_node, fbx_scene)

                self.context = None

                recursive_add_nodes(
                    [child_ptr.data for child_ptr in source_node.children.data],
                    fbx_node
                )

        self.debug('building node tree')
        recursive_add_nodes([child_ptr.data for child_ptr in source.root_node.children.data],
                            fbx_scene.GetRootNode())

    def _export(self, scene: fbx.FbxScene, dest):

        self.debug('exporting fbx scene')

        fbx_exporter = fbx.FbxExporter.Create(MEMORY_MANAGER, '')
        fbx_exporter.Initialize(dest, -1, MEMORY_MANAGER.GetIOSettings())
        fbx_exporter.Export(scene)
        fbx_exporter.Destroy()

    def convert(self) -> fbx.FbxScene:
        mdb_source = Mdb.from_file(self.source.file.full_file_name)  # TODO add full file path
        dest_scene = fbx.FbxScene.Create(MEMORY_MANAGER, mdb_source.root_node.node_name.string)
        self._build_fbx_scene(dest_scene, mdb_source)
        return dest_scene

    def convert_and_export(self, destination: Directory):
        fbx_scene = self.convert()
        self._export(fbx_scene, destination.full_path)
        fbx_scene.Destroy()


if __name__ == '__main__':
    Mdb2FbxConverter(
        Resource(sys.argv[1]),
        Settings.from_cmd_args(sys.argv[3:])
    ).convert_and_export(Directory(sys.argv[2]))
