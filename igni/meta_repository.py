"""
this repository saves meta data from export to an sqlite database
"""

import sqlite3
from .resources import Directory
import os.path
import time


def generate_name():
    return 'export_session_' + str(int(time.time())) + '.db'


def create_meta_db(directory: Directory) -> sqlite3.Connection:

    return sqlite3.connect(os.path.join(directory.full_path, generate_name()))
