"""
this repository saves meta data from export to an sqlite database
"""

import sqlite3
from .settings import Settings
from .logging_util import IgniLogger


# map mdb textures of particular type to particular properties of an fbx material
class ExportMetadataRepository:
    TABLES = {
        'material_configuration': {
            'name': 'material_configuration',
            'columns': (
                ('file', 'TEXT', 'NOT NULL'),
                ('mesh', 'TEXT', 'NOT NULL'),
                ('shader', 'TEXT', 'NOT NULL'),
                ('material', 'TEXT', 'NOT NULL')
            ),
            'primary_key': ('file', 'mesh')
        },

        'mdb_node_meta': {
            'name': 'mdb_node_meta',
            'columns': (
                ('file', 'TEXT', 'NOT NULL'),
                ('node', 'TEXT', 'NOT NULL'),
                ('node_type', 'TEXT', 'NOT NULL'),
                ('node_meta', 'TEXT')
            ),
            'primary_key': ('file', 'node')
        },

        'mdb_file_meta': {
            'name': 'mdb_file_meta',
            'columns': (
                ('file', 'TEXT', 'NOT NULL'),
                ('node_count', 'INTEGER', 'NOT NULL'),
                ('mesh_count', 'INTEGER', 'NOT NULL'),
                ('material_count', 'INTEGER', 'NOT NULL'),
                ('bone_count', 'INTEGER', 'NOT NULL'),
                ('animation_count', 'INTEGER', 'NOT NULL'),
                ('tri_count', 'INTEGER', 'NOT NULL')
            ),
            'primary_key': ('file',)
        }
    }

    def __init__(self):
        self.logger = None
        self.connection = None

    def db_setup(self):
        """
        set up tables in the database, if none exist
        """

        def _get_create_table_statement_(table_spec):
            columns = [' '.join(col_spec) for col_spec in table_spec['columns']]
            columns = ','.join(columns)

            statement = 'CREATE TABLE IF NOT EXISTS {table_name} ({columns}'.format(table_name=table_spec['name'],
                                                                                    columns=columns)
            if 'primary_key' in table_spec and table_spec['primary_key'] is not None:
                statement += ',' + 'PRIMARY KEY(' + ','.join(table_spec['primary_key']) + '))'
            else:
                statement += ')'

            return statement

        [self._sql_exec_(_get_create_table_statement_(table_spec)) for table_spec in self.TABLES.values()]

    def _sql_exec_(self, sql):
        if self.connection is None:
            raise Exception('connection is null')

        self.logger.debug('executing sql statement: {}'.format(sql))

        cursor = self.connection.cursor()
        cursor.execute(sql)
        self.connection.commit()
        return cursor

    def configure(self, db_path):
        self.logger = None

        if self.connection is not None:
            self.connection.close()

        self.connection = sqlite3.connect(db_path)
        self.db_setup()

    def _get_col_spec_(self, table, col):
        columns = self.TABLES[table]['columns']
        columns = [col_ for col_ in columns if col_[0] == col]
        if len(columns) == 0:
            raise Exception('col {} in table {} not found'.format(col, table))
        return columns[0]

    def _does_entity_exist_(self, entity, table: str):
        primary_keys = self.TABLES[table]['primary_key']
        primary_key_equality_conditions = " AND ".join(
            [primary_key + "=" +
             self._prepare_data_type_(entity[primary_key], self._get_col_spec_(table, primary_key)[1])
             for primary_key in primary_keys])

        cursor = self._sql_exec_("SELECT count(*) FROM {table_name} WHERE {conditions}".format(
            table_name=table,
            conditions=primary_key_equality_conditions
        ))

        return cursor.fetchall()[0][0] > 0

    def _remove_entity_(self, entity, table: str):
        primary_keys = self.TABLES[table]['primary_key']
        primary_key_equality_conditions = " AND ".join(
            [primary_key + "=" +
             self._prepare_data_type_(entity[primary_key], self._get_col_spec_(table, primary_key)[1])
             for primary_key in primary_keys])

        self._sql_exec_("DELETE FROM {table_name} WHERE {conditions}".format(
            table_name=table,
            conditions=primary_key_equality_conditions
        ))

    def _save_entity_(self, entity: dict, table: str):
        which_columns = ",".join([key for key, val in entity.items() if val is not None])
        which_values = ",".join(
            [self._prepare_data_type_(val, self._get_col_spec_(table, key)[1])
             for key, val in entity.items() if val is not None])

        self._sql_exec_("INSERT INTO {table_name} ({columns}) VALUES ({values})".format(table_name=table,
                                                                                        columns=which_columns,
                                                                                        values=which_values))

    def _overwrite_entity_(self, entity: dict, table: str):
        if self._does_entity_exist_(entity, table):
            self._remove_entity_(entity, table)
        self._save_entity_(entity, table)

    @staticmethod
    def _prepare_data_type_(variable, sqlite_dtype: str):
        variable_ = str(variable)
        if sqlite_dtype.lower() == 'text':
            if "\"" in variable_ and not "'" in variable_:
                pass
            elif "'" in variable_ and not "\"" in variable_:
                variable_ = variable_.replace("'", "\"")
            elif "\"" in variable_ and "'" in variable_:
                raise Exception('cannot save string with mixed single and double quotes')
            variable_ = "'" + variable_ + "'"
        return variable_

    def save_material_spec(self, file_name, mesh_name, material: dict):
        self._overwrite_entity_({
            'file': file_name,
            'mesh': mesh_name,
            'shader': material['shader'],
            'material': material
        }, 'material_configuration')

    def save_mdb_node_meta(self, file_name, node_name, node_type, node_meta: dict = None):
        self._overwrite_entity_({
            'file': file_name,
            'node': node_name,
            'node_type': node_type,
            'node_meta': node_meta
        }, 'mdb_node_meta')

    def save_mdb_file_meta(self,
                           file_name: str,
                           node_count,
                           mesh_count,
                           material_count,
                           bone_count,
                           animation_count,
                           tri_count):
        self._overwrite_entity_({
            'file': file_name,
            'node_count': node_count,
            'mesh_count': mesh_count,
            'material_count': material_count,
            'bone_count': bone_count,
            'animation_count': animation_count,
            'tri_count': tri_count
        }, 'mdb_file_meta')


EXPORT_METADATA_REPOSITORY = ExportMetadataRepository()
