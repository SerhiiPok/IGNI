from mdb import Mdb
import fbx
import sys

sys.path.append("E:\\projects\\the_witcher\\content_pipeline\\igni\\utils\\")
from fbxu import FBX


class _MdbFbxBridge:

    @classmethod
    def node(cls,
             mdb_node: Mdb.Node,
             fbx_parent_node: fbx.FbxNode = None) -> fbx.FbxNode:
        # TODO translation, rotation, and others
        fbx_node: fbx.FbxNode = FBX.node()
        if fbx_parent_node is not None:
            fbx_parent_node.AddChild(fbx_node)
        return fbx_node

    @classmethod
    def transfer_trimesh_data(cls,
                              mdb_source: Mdb.Node,
                              fbx_dest: fbx.FbxNode):
        # TODO in the below both parts are always evaluated?
        mesh: fbx.FbxMesh = fbx_dest.GetMesh() \
            if fbx_dest.GetMesh() is not None \
            else FBX.add_mesh(fbx_dest)

        # source data
        mdb_verts = mdb_source.node_data.mesh_data.vertices.data
        mdb_faces = mdb_source.node_data.mesh_data.faces_array_pointer.data

        # vertices
        mesh.InitControlPoints(len(mdb_verts))
        for i in range(0, len(mdb_verts)):
            vertex = mdb_verts[i]
            mesh.SetControlPointAt(
                fbx.FbxVector4(vertex.x, vertex.y, vertex.z, 0.0),
                i
            )

        # faces
        for i in range(0, len(mdb_faces)):
            face = mdb_faces[i]
            mesh.BeginPolygon()
            mesh.AddPolygon(face.c1)
            mesh.AddPolygon(face.c2)
            mesh.AddPolygon(face.c3)
            mesh.EndPolygon()

    @classmethod
    def transfer_node_data(cls,
                           mdb_source: Mdb.Node,
                           fbx_dest: fbx.FbxNode):
        if mdb_source.node_type == Mdb.NodeType.trimesh:
            _MdbFbxBridge.transfer_trimesh_data(mdb_source, fbx_dest)
        else:
            print('cannot transfer data for the node of an unhandled type')

    @classmethod
    def scene(cls, mdb: Mdb) -> fbx.FbxScene:
        fbx_scene: fbx.FbxScene = FBX.scene()

        # transfer the nodes
        def _recursive_convert_nodes_(mdb_node: Mdb.Node,
                                      fbx_parent: fbx.FbxNode):
            fbx_node = _MdbFbxBridge.node(mdb_node, fbx_parent)
            _MdbFbxBridge.transfer_node_data(mdb_node, fbx_node)
            [_recursive_convert_nodes_(node_ptr.data, fbx_node)
             for node_ptr in mdb_node.children.data]

        _recursive_convert_nodes_(mdb.root_node, fbx_scene.GetRootNode())

        return fbx_scene


def from_mdb(mdb: Mdb) -> fbx.FbxScene:
    return _MdbFbxBridge.scene(mdb)


def from_bytes(byte_stream) -> fbx.FbxScene:
    return from_mdb(Mdb.from_bytes(byte_stream))


def from_path(path) -> fbx.FbxScene:
    return from_mdb(Mdb.from_file(path))


def convert(source, dest):
    scene = from_path(source)
    FBX.export(scene, dest)
    scene.Destroy()


if __name__ == '__main__':
    # TODO proper handling of command line arguments
    # TODO redesign how the files will be launched
    source_path = sys.argv[1]
    dest_path = sys.argv[2]
    convert(source_path, dest_path)