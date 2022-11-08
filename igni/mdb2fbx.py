from mdb import Mdb
import fbx
import sys
import logging

MEMORY_MANAGER = fbx.FbxManager.Create()


class OnModuleClose:

    def __del__(self):
        print('on module close called')
        MEMORY_MANAGER.Destroy()


MODULE_CLOSE_INTERCEPTOR = OnModuleClose()


LOGGER = logging.getLogger(__name__)


# logging context provides a way to put additional debug information into logs
class LoggingContext:

    def __init__(self):
        self.file = ''
        self.obj = None

    def file(self, file_name):
        self.file = file_name
        return self

    def object(self, obj):
        self.obj = obj
        return self

    def clear(self):
        self.file = ''
        self.obj = None
        return self

    def __call__(self, msg):
        # decorate the log message
        prefix = ''
        if self.file != '':
            prefix = prefix + 'file: {} '.format(self.file)
        if self.obj is not None:
            if isinstance(self.obj, Mdb.Node):
                prefix = prefix + 'node: {} '.format(self.obj.node_name.string)
        return prefix + msg


LOGGING_CONTEXT = LoggingContext()


# a wrapper class for trimesh (triangular mesh) objects
class _Trimesh:

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


def _log_trimesh(trimesh: _Trimesh):

    if len(trimesh.vertices) == 0:
        LOGGER.warning(LOGGING_CONTEXT('mesh vertices array is empty'))
        return

    if len(trimesh.faces) == 0:
        LOGGER.warning(LOGGING_CONTEXT('mesh faces are not defined'))
    if len(trimesh.normals) == 0:
        LOGGER.warning(LOGGING_CONTEXT('mesh normals are not defined'))
    # TODO uvs

    if len(trimesh.vertices) != len(trimesh.normals) or len(trimesh.vertices) != len(trimesh.uvs):
        LOGGER.warning(LOGGING_CONTEXT('number of mesh vertices is not equal to number of normals or uvs'))

    LOGGER.debug(LOGGING_CONTEXT('mesh has {} faces and {} vertices'.format(
        len(trimesh.faces), len(trimesh.vertices))))


# a wrapper class for mdb materials
class _Material:

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


class ConverterConfiguration:

    def __init__(self):
        self.skip_nodes = None
        self.texture_path_handling = None


def _build_fbx_mesh(fbx_mesh: fbx.FbxMesh, trimesh: _Trimesh):

    # -- check input parameters
    _log_trimesh(trimesh)

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


def _build_fbx_node(fbx_node: fbx.FbxNode, source_node: Mdb.Node, fbx_scene: fbx.FbxScene):

    fbx_node.SetName(source_node.node_name.string)

    LOGGER.debug(LOGGING_CONTEXT('node type is {}'.format(source_node.node_type.name)))

    # do translation, rotation, etc.
    if source_node.node_type == Mdb.NodeType.trimesh or \
            source_node.node_type == Mdb.NodeType.skin:
        mesh = fbx.FbxMesh.Create(fbx_scene, '')
        fbx_node.AddNodeAttribute(mesh)
        _build_fbx_mesh(mesh,
                        _Trimesh(source_node))
    else:
        LOGGER.debug(LOGGING_CONTEXT('this node type is not handled'))


def _build_fbx_scene(fbx_scene: fbx.FbxScene, source: Mdb):

    LOGGER.debug(LOGGING_CONTEXT('start building fbx scene'))

    def recursive_add_nodes(source_nodes, under_parent: fbx.FbxNode):
        for source_node in source_nodes:

            LOGGING_CONTEXT.object(source_node)

            fbx_node = fbx.FbxNode.Create(fbx_scene, '')
            under_parent.AddChild(fbx_node)
            _build_fbx_node(fbx_node, source_node, fbx_scene)

            LOGGING_CONTEXT.object(None)

            recursive_add_nodes(
                [child_ptr.data for child_ptr in source_node.children.data],
                fbx_node
            )

    LOGGER.debug(LOGGING_CONTEXT('building node tree'))
    recursive_add_nodes([child_ptr.data for child_ptr in source.root_node.children.data],
                        fbx_scene.GetRootNode())


def export(scene: fbx.FbxScene, dest):

    LOGGER.debug(LOGGING_CONTEXT('exporting fbx scene'))

    fbx_exporter = fbx.FbxExporter.Create(MEMORY_MANAGER, '')
    fbx_exporter.Initialize(dest, -1, MEMORY_MANAGER.GetIOSettings())
    fbx_exporter.Export(scene)
    fbx_exporter.Destroy()


def from_mdb(mdb: Mdb) -> fbx.FbxScene:
    fbx_scene = fbx.FbxScene.Create(MEMORY_MANAGER, mdb.root_node.node_name.string)
    _build_fbx_scene(fbx_scene, mdb)
    return fbx_scene


def from_bytes(byte_stream) -> fbx.FbxScene:
    return from_mdb(Mdb.from_bytes(byte_stream))


def from_path(path) -> fbx.FbxScene:
    LOGGING_CONTEXT.clear().file(path)
    return from_mdb(Mdb.from_file(path))


def convert(source, dest):
    scene = from_path(source)
    export(scene, dest)
    scene.Destroy()


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


if __name__ == '__main__':
    # TODO proper handling of command line arguments
    # TODO redesign how the files will be launched
    source_path = sys.argv[1]
    dest_path = sys.argv[2]
    convert(source_path, dest_path)