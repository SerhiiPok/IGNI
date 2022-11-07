import fbx as _fbx


class _FbxUtil:

    """
    this helper class initializes fbx objects and does
    memory management
    """

    def __init__(self):
        self.memory_manager = _fbx.FbxManager.Create()
        self.scenes = []

    # destroy all scenes available so far in this instance
    def mem_clear(self):
        [scene.Destroy() for scene in self.scenes()]

    def scene(self) -> _fbx.FbxScene:
        """
        :return: new empty fbx scene
        """
        scene = _fbx.FbxScene.Create(self.memory_manager, '')
        self.scenes.append(scene)
        return scene

    def node(self) -> _fbx.FbxNode:
        """
        :return: new empty fbx node
        """
        return _fbx.FbxNode.Create(self.memory_manager, '')

    def export(self, scene: _fbx.FbxScene, destination):
        exporter: _fbx.FbxExporter = _fbx.FbxExporter.Create(self.memory_manager, '')
        exporter.Initialize(destination, -1, self.memory_manager.GetIOSettings())
        exporter.Export(scene)
        exporter.Destroy()

    def add_mesh(self, node: _fbx.FbxNode) -> _fbx.FbxMesh:
        """
        create empty mesh and add to specified node
        :return: the created mesh
        """
        mesh_attribute = _fbx.FbxMesh.Create(self.memory_manager, '')
        node.AddNodeAttribute(mesh_attribute)
        return mesh_attribute

    def open(self, source):
        pass

    def __del__(self):
        self.memory_manager.Destroy()


FBX = _FbxUtil()
