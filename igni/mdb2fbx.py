from .mdb import Mdb
import os
import fbx
import sys
import logging
from .settings import Settings
from .resources import Directory, File, Resource, ResourceTypes

LOGGER = logging.getLogger(__name__)

MEMORY_MANAGER = fbx.FbxManager.Create()


class OnModuleClose:

    def __del__(self):
        LOGGER.debug('destroying fbx memory manager...')
        MEMORY_MANAGER.Destroy()


MODULE_CLOSE_INTERCEPTOR = OnModuleClose()


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
                self.uv_sets['UvSet{}'.format(i)] = [[c.u, c.v] for c in uv_array_pointer.data]


# a wrapper class for mdb materials
class Material:

    def __init__(self, material_descr: Mdb.Material):
        if material_descr is None:
            raise Exception('tried to create material wrapper but material description is None')

        self.shader = ''
        self.textures = {}
        self.bumpmaps = {}
        self.properties = {}

        self.parse_data(material_descr.material_spec)

    def __str__(self):
        data = {'shader': self.shader,
                'textures': self.textures,
                'bumpmaps': self.bumpmaps,
                'properties': self.properties}
        return str(data)

    def parse_data(self, material_spec: list):

        def line_clean_up(line):
            return line.replace('\\r\\n', ' ').lstrip().rstrip()

        for line in material_spec:
            l_ = line_clean_up(line)

            if len(l_) == 0:
                continue

            parts = l_.split(' ')
            descriptor = parts[0]

            if descriptor == 'shader':
                if len(parts) != 2:
                    raise Exception('unexpected shader specification: {}'.format(l_))
                else:
                    self.shader = parts[1]

            elif descriptor == 'texture':
                if len(parts) != 3:
                    raise Exception('unexpected texture specification: {}'.format(l_))
                else:
                    if parts[1] in self.textures:
                        raise Exception('duplicated texture found: {}'.format(l_))
                    self.textures[parts[1]] = parts[2]

            elif descriptor == 'bumpmap':
                if len(parts) != 3:
                    raise Exception('unexpected bumpmap specification: {}'.format(l_))
                else:
                    if parts[1] in self.bumpmaps:
                        raise Exception('duplicated bumpmap found: {}'.format(l_))
                    self.bumpmaps[parts[1]] = parts[2]

            elif descriptor == 'float' or descriptor == 'string':
                if len(parts) != 3:
                    raise Exception('unexpected property specification: {}'.format(l_))
                else:
                    self.properties[parts[1]] = parts[2]

            elif descriptor == 'vector':
                if len(parts) != 6:
                    raise Exception('unexpected vector property specification: {}'.format(l_))
                else:
                    self.properties[parts[1]] = (parts[2], parts[3], parts[4], parts[5])

            else:
                raise Exception('unexpected material line: {}'.format(l_))


MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE = {
    'texture-handling': {
        'method': str,
        'dest-dir': Directory
    },
    'skip-shadowbones': bool,
    'logging': {
        'level': str
    },
    'unit-conversion-factor': float
}

MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS = {
    'texture-handling': {
        'method': 'with-file'
    },
    'skip-shadowbones': True,
    'logging': {
        'level': 'INFO'
    },
    'unit-conversion-factor': 100.0
}


class Mdb2FbxConverter:

    def _get_context_inf(self):
        if isinstance(self.context, Mdb.Node):
            return self.context.node_name.string
        else:
            return ''

    # logging at four levels
    def _decorate_message(self, msg):
        inf = {
            'input': str(self.source.file),
            'msg': msg
        }  # TODO file must have full file path attribute

        if self.context is not None:
            inf['context'] = {
                'type': str(type(self.context)),
                'info': self._get_context_inf()
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
            .set('logging.level', settings.get('logging.level', logging.WARNING)) \
            .set('unit-conversion-factor', settings.get('unit-conversion-factor', 100.0))

        if settings.get('texture-handling.method') == 'dest-dir':
            self.settings.set('texture-handling.dest-dir', settings.get('texture-handling.dest-dir'))

    def __init__(self, source: Resource, settings: Settings = Settings()):
        assert (source.resource_type == ResourceTypes.MDB or source.resource_type == ResourceTypes.MBA)
        self.source: Resource = source
        self.settings: Settings = Settings()
        self.context = None

        self._init_settings(settings)

        LOGGER.setLevel(self.settings.get('logging.level'))

    def _log_trimesh(self, trimesh: Trimesh):

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

    def _build_fbx_mesh(self, fbx_mesh: fbx.FbxMesh, trimesh: Trimesh):

        # -- check input parameters
        self._log_trimesh(trimesh)

        # -- build mesh data
        fbx_mesh.InitControlPoints(len(trimesh.vertices))
        unit_conversion_factor = self.settings.get('unit-conversion-factor')
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

                # meshes reserved for casting shadows can be skipped on request of user
                if 'shadowbone' in source_node.node_name.string:
                    if self.settings.get('skip-shadowbones'):
                        if len(source_node.children.data) > 0:
                            self.warn(
                                'shadowbones are skipped but this one has children which will result in data loss')
                        else:
                            continue

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
        fbx_exporter.Initialize(os.path.join(dest, self.source.file.name), -1, MEMORY_MANAGER.GetIOSettings())
        fbx_exporter.Export(scene)
        fbx_exporter.Destroy()

    def convert(self) -> fbx.FbxScene:
        mdb_source = Mdb.from_file(str(self.source.file))  # TODO add full file path
        dest_scene = fbx.FbxScene.Create(MEMORY_MANAGER, mdb_source.root_node.node_name.string)
        self._build_fbx_scene(dest_scene, mdb_source)
        return dest_scene

    def convert_and_export(self, destination: Directory):
        fbx_scene = self.convert()
        self._export(fbx_scene, destination.full_path)
        fbx_scene.Destroy()


if __name__ == '__main__':
    Mdb2FbxConverter(
        Resource(File(sys.argv[1])),
        Settings(MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE).
            accept_tree(MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS).
            accept_cmd_args(sys.argv[3:])
    ).convert_and_export(Directory(sys.argv[2]))
