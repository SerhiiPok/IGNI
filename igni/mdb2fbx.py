from .mdb import Mdb
import os
import fbx
import sys
import logging
from .settings import Settings
from .resources import Directory, File, Resource, ResourceTypes
from .mdbutil import MdbWrapper, Material, Trimesh

LOGGER = logging.getLogger(__name__)

MEMORY_MANAGER = fbx.FbxManager.Create()


class OnModuleClose:

    def __del__(self):
        LOGGER.debug('destroying fbx memory manager...')
        MEMORY_MANAGER.Destroy()


MODULE_CLOSE_INTERCEPTOR = OnModuleClose()


MDB_2_FBX_CONVERTER_SETTINGS_TEMPLATE = {
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
}

MDB_2_FBX_CONVERTER_DEFAULT_SETTINGS = {
    'texture-conversion': {
        'format': 'png'
    },
    'skip-nodes': {
        'if-name-contains': 'Shadowbone'
    },
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
