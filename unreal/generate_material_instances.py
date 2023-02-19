"""
you can run this file in unreal engine if you activated unreal engine python plugin
to generate and assign materials to all imported meshes
"""

import unreal
import sys
import sqlite3

program_args = sys.argv

if len(program_args) < 2:
    raise Exception("missing mandatory script argument: path to igni directory")
IGNI_BASE = program_args[1]

if len(program_args) < 3:
    raise Exception("missing mandatory script argument: path to database with material configurations")
MATERIAL_CONFIG_DB = sqlite3.connect(program_args[2])

MATERIAL_DEST_DIR = None
if len(program_args) > 3:
    MATERIAL_DEST_DIR = program_args[2]


class FilePathService:

    @staticmethod
    def _split_path_(object_path: str):
        last_slash_ind = object_path.rfind('/')
        if last_slash_ind >= 0:
            return object_path[0:last_slash_ind], object_path[last_slash_ind + 1:]
        else:
            return '', object_path

    @classmethod
    def object_path_to_file_path(cls, object_path):
        file_path, file_name = cls._split_path_(object_path)
        if '.' in file_name:
            parts = file_name.split('.')
            if len(parts) == 2 and parts[0] == parts[1]:
                return file_path + '/' + parts[0]
            else:
                return object_path
        else:
            return object_path

    @classmethod
    def object_paths_to_file_paths(cls, object_paths):
        return [cls.object_path_to_file_path(object_path) for object_path in object_paths]


class WitcherAssetRepository:

    def __init__(self, witcher_content_base_directory):

        self.base_dir = witcher_content_base_directory

        self.static_meshes = {}
        self.skeletal_meshes = {}
        self.textures = {}

        self._init_data_()

    def list_asset_file_paths(self):

        def _split_path_(object_path: str):
            last_slash_ind = object_path.rfind('/')
            if last_slash_ind >= 0:
                return object_path[0:last_slash_ind], object_path[last_slash_ind+1:]
            else:
                return '', object_path

        def _object_path_to_file_path_(object_path: str):
            file_path, file_name = _split_path_(object_path)
            if '.' in file_name:
                parts = file_name.split('.')
                if len(parts) == 2 and parts[0] == parts[1]:
                    return file_path + '/' + parts[0]
                else:
                    return object_path
            else:
                return object_path

        return [_object_path_to_file_path_(object_path) for object_path in unreal.EditorAssetLibrary.list_assets(self.base_dir, True, True)]

    def _init_data_(self):

        def classify_and_append(asset, repository):
            if isinstance(asset, unreal.StaticMesh):
                repository.static_meshes[asset.get_name()] = unreal.StaticMesh.cast(asset)
            elif isinstance(asset, unreal.SkeletalMesh):
                repository.skeletal_meshes[asset.get_name()] = unreal.SkeletalMesh.cast(asset)
            elif isinstance(asset, unreal.Texture):
                repository.textures[asset.get_name()] = unreal.Texture.cast(asset)

        [classify_and_append(unreal.EditorAssetLibrary.load_asset(file_path), self) for file_path in
         FilePathService.object_paths_to_file_paths(unreal.EditorAssetLibrary.list_assets(self.base_dir, True, True))]


class ShaderRepository:

    def __init__(self, witcher_content_base_directory):

        self.base_dir = witcher_content_base_directory
        self.shaders = {}
        self._init_data_()

    def _init_data_(self):
        setup_dir = self.base_dir + '/' + 'Setup' + '/' + 'Shaders'
        if not unreal.EditorAssetLibrary.does_directory_exist(setup_dir):
            raise Exception('no Setup directory found in igni base folder')

        for file_path in FilePathService.object_paths_to_file_paths(unreal.EditorAssetLibrary.list_assets(setup_dir, True, True)):
            asset = unreal.EditorAssetLibrary.load_asset(file_path)
            if isinstance(asset, unreal.Material):
                self.shaders[asset.get_name()] = unreal.Material.cast(asset)

        if len(self.shaders) == 0:
            raise Exception('no shaders configured')


class ModelMaterialDataRepository:

    def __init__(self):
        self.specifications = {}  # file_name: specification
        self._init_data_()

    def _init_data_(self):
        cur = MATERIAL_CONFIG_DB.cursor()
        cur.execute('select file, mesh, material from material_configuration')

        for row in cur.fetchall():
            self.specifications[row[0] + '_' + row[1]] = Material(eval(row[2]))

    def find_material_specification(self, model_name):
        spec = self.specifications.get(model_name, None)
        if spec is None:
            raise Exception('no material specification found for model "{}"'.format(model_name))
        return spec


class Material:

    def __init__(self, material_dict_specification):

        self.shader = material_dict_specification['shader']
        self.textures = material_dict_specification['textures']
        self.parameters = material_dict_specification['parameters']


class MaterialInstanceSetupService:

    def __init__(self, witcher_base_content_directory, witcher_asset_repository, output_dir=None):
        self.shader_repository = ShaderRepository(witcher_base_content_directory)
        self.output_dir = output_dir
        self.asset_repository = witcher_asset_repository

        self._asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        self._material_instance_factory = unreal.MaterialInstanceConstantFactoryNew()

    def _create_material_instance_(self, destination, material_instance_name):
        if unreal.EditorAssetLibrary.does_asset_exist(destination + '/' + material_instance_name):
            unreal.EditorAssetLibrary.delete_asset(destination + '/' + material_instance_name)

        return self._asset_tools.create_asset(material_instance_name,
                                              destination,
                                              unreal.MaterialInstanceConstant,
                                              self._material_instance_factory)

    def _create_material_instance_for_asset_(self, asset):
        dest_dir = self.output_dir if self.output_dir is not None else \
            unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(asset)
        dest_dir = dest_dir[0:dest_dir.rfind('/')]

        new_material_name = asset.get_name() + '_mat'
        return self._create_material_instance_(dest_dir, new_material_name)

    def _configure_material_(self, material: unreal.MaterialInstanceConstant, material_spec: Material):
        mlib = unreal.MaterialEditingLibrary

        def _get_parent_or_fail():
            parent = self.shader_repository.shaders.get(material_spec.shader, None)
            if parent is None:
                raise Exception('could not find parent material for shader of type "{}"'.format(material_spec.shader))
            return parent

        def _get_texture_or_fail(tex_name):
            texture = self.asset_repository.textures.get(tex_name, None)
            if texture is None:
                raise Exception('could not locate texture with name "{}"'.format(tex_name))
            return texture

        parent_material = _get_parent_or_fail()

        mlib.set_material_instance_parent(material, parent_material)

        for texture_parameter_name in [str(name) for name in mlib.get_texture_parameter_names(parent_material)]:
            mlib.set_material_instance_texture_parameter_value(
                material,
                texture_parameter_name,
                _get_texture_or_fail(material_spec.textures[texture_parameter_name]))

    def _assign_material_(self, asset, mat_instance):
        if isinstance(asset, unreal.StaticMesh):
            unreal.StaticMesh.cast(asset).set_material(0, mat_instance)
        elif isinstance(asset, unreal.SkeletalMesh):
            unreal.StaticMesh.cast(asset).set_material(0, mat_instance) # TODO
        else:
            raise Exception('cannot assign material for the asset type of asset "{}"'.format(asset.get_name()))

    def set_up_material_instance(self, asset, material: Material):
        mat_instance: unreal.MaterialInstanceConstant = self._create_material_instance_for_asset_(asset)
        self._configure_material_(mat_instance, material)
        self._assign_material_(asset, mat_instance)


witcher_asset_repository = WitcherAssetRepository(IGNI_BASE)
model_material_data_repository = ModelMaterialDataRepository()
material_instance_setup_service = MaterialInstanceSetupService(IGNI_BASE, witcher_asset_repository)

all_meshes = witcher_asset_repository.static_meshes
all_meshes.update(witcher_asset_repository.skeletal_meshes)
all_meshes = [(key, val) for key, val in all_meshes.items()]

for mesh_name, mesh in all_meshes:
    try:
        material_instance_setup_service.set_up_material_instance(
            mesh,
            model_material_data_repository.find_material_specification(mesh_name)
        )
    except Exception as e:
        unreal.log_error(e)
