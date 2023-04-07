"""
you can run this file in unreal engine if you activated unreal engine python plugin
to run batch import of witcher content
"""

import unreal
import sys
from pathlib import Path

program_args = sys.argv  # root directory for imports

if len(program_args) < 2:
    raise Exception("missing mandatory script argument: path to root directory")

CONTENT_ROOT = Path(program_args[1])
if not CONTENT_ROOT.exists():
    raise Exception("supplied an invalid root directory")

DESTINATION_ROOT = Path("/Game/Igni/GameContent")

EXTENSIONS_TO_IMPORT = [
    '.png'
]

import_tasks = []

for path in CONTENT_ROOT.glob('**/*'):
    if path.is_file and path.suffix in EXTENSIONS_TO_IMPORT and 'Levels' not in path.parts:
        import_task = unreal.AssetImportTask()
        import_task.automated = True
        import_task.save = False
        import_task.destination_path = (DESTINATION_ROOT / (path.parent.relative_to(CONTENT_ROOT))).as_posix()
        import_task.filename = str(path)

        import_tasks.append(import_task)

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(import_tasks)
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
    save_map_packages=False,
    save_content_packages=True
)
