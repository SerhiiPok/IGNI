from mdb import Mdb
import fbx
import sys


MEMORY_MANAGER = fbx.FbxManager.Create()


class OnModuleClose:

    def __del__(self):
        print('on module close called')
        MEMORY_MANAGER.Destroy()


MODULE_CLOSE_INTERCEPTOR = OnModuleClose()


def _build_fbx_mesh(fbx_mesh: fbx.FbxMesh, vertices, faces, normals, uvs):

    fbx_mesh.InitControlPoints(len(vertices))
    for i in range(0, len(vertices)):
        vertex = vertices[i]
        fbx_mesh.SetControlPointAt(
            fbx.FbxVector4(vertex[0], vertex[1], vertex[2], 0.0),
            i
        )

    for i in range(len(faces)):
        face = faces[i]
        fbx_mesh.BeginPolygon()
        for vertex_index in face:
            fbx_mesh.AddPolygon(vertex_index)
        fbx_mesh.EndPolygon()

    for uv_set in uvs:
        uv_element: fbx.FbxLayerElementUV = fbx_mesh.CreateElementUV(uv_set)
        uv_element.SetMappingMode(fbx.FbxLayerElementUV.eByControlPoint)
        uv_element.SetReferenceMode(fbx.FbxLayerElement.eDirect)

        for uv_coord in uvs[uv_set]:
            uv_element.GetDirectArray().Add(fbx.FbxVector2(uv_coord[0], uv_coord[1]))


def _build_fbx_node(fbx_node: fbx.FbxNode, source_node: Mdb.Node, fbx_scene: fbx.FbxScene):

    fbx_node.SetName(source_node.node_name.string)

    # do translation, rotation, etc.
    if source_node.node_type == Mdb.NodeType.trimesh or \
            source_node.node_type == Mdb.NodeType.skin:
        mesh = fbx.FbxMesh.Create(fbx_scene, '')
        fbx_node.AddNodeAttribute(mesh)
        _build_fbx_mesh(mesh,
                        [[v.x, v.y, v.z] for v in source_node.node_data.vertices.data],
                        [[f.vert1, f.vert2, f.vert3] for f in source_node.node_data.faces.data],
                        [[n.x, n.y, n.z] for n in source_node.node_data.normals.data],
                        {'uv_set_1':[[c.u, c.v] for c in source_node.node_data.uvs[0].data]})
    else:
        pass


def _build_fbx_scene(fbx_scene: fbx.FbxScene, source: Mdb):

    def recursive_add_nodes(source_nodes, under_parent: fbx.FbxNode):
        for source_node in source_nodes:
            fbx_node = fbx.FbxNode.Create(fbx_scene, '')
            under_parent.AddChild(fbx_node)
            _build_fbx_node(fbx_node, source_node, fbx_scene)

            recursive_add_nodes(
                [child_ptr.data for child_ptr in source_node.children.data],
                fbx_node
            )

    recursive_add_nodes([child_ptr.data for child_ptr in source.root_node.children.data],
                        fbx_scene.GetRootNode())


def export(scene: fbx.FbxScene, dest):
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
    return from_mdb(Mdb.from_file(path))


def convert(source, dest):
    scene = from_path(source)
    export(scene, dest)
    scene.Destroy()


if __name__ == '__main__':
    # TODO proper handling of command line arguments
    # TODO redesign how the files will be launched
    source_path = sys.argv[1]
    dest_path = sys.argv[2]
    convert(source_path, dest_path)