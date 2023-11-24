import hashlib
import os
import sys

os.environ['TZ'] = 'UTC'  # Set the time zone to UTC for consistency
os.environ['SOURCE_DATE_EPOCH'] = '0'  # Set the source date epoch to a fixed value (e.g., 0)
os.environ['IGNORE_VARS'] = 'true'


def check_env_variables():
    again = True
    while len(sys.argv) > 1 and again:
        again = False
        for index in range(1, len(sys.argv)):
            value = sys.argv[index]
            v_index = value.find("=")
            if v_index > 0:
                os.environ[value[0:v_index:]] = value[v_index + 1::]
                del sys.argv[index]
                again = True
                break


check_env_variables()

import zipfile
from types import ModuleType
from typing import Any, Optional, Set
from zipfile import ZipInfo

src_name = os.path.realpath(f"{__file__}/../src")
if src_name not in sys.path:
    sys.path.insert(0, src_name)

from bean import set_resettable

set_resettable(False)

import app
from bean.beans import load_all_lazy

verbose = False

TIME_STAMP = (2020, 2, 2, 2, 2, 2)
EMPTY = bytes()


def create_zip_info(file_name: str, archive_name: str) -> ZipInfo:
    zip_info = ZipInfo.from_file(file_name, archive_name)
    zip_info.date_time = TIME_STAMP
    zip_info.extra = EMPTY
    zip_info.create_system = 0
    return zip_info


def build_archive_name(file_name: str, base_path: str) -> str:
    name = os.path.relpath(file_name, base_path)
    if os.path.sep != '/':
        name = name.replace(os.path.sep, '/')
    return name


class MyZipper:
    def __init__(self, file_name: str, src_dir: str):
        self.zip = zipfile.ZipFile(file_name, "w")
        self.src_dir = src_dir
        self.entries = set()
        self.paths_added = set()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.zip.__exit__(exc_type, exc_val, exc_tb)

    def __write(self, file_name: str):
        archive_name = build_archive_name(file_name, self.src_dir)
        if os.path.isdir(file_name):
            data = EMPTY
            archive_name += '/'
        else:
            with open(file_name, "rb") as f:
                data = f.read()

        zip_info = create_zip_info(file_name, archive_name)
        self.zip.writestr(zip_info, data)

    def check_dirs(self, archive_name: str):
        values = archive_name.split('/')
        if len(values) == 1:
            return
        file_path = self.src_dir
        values = values[0:len(values) - 1:]
        path = ""
        for value in values:
            file_path = os.path.join(file_path, value)
            path += value + '/'
            if path not in self.paths_added:
                self.entries.add(file_path)
                self.paths_added.add(path)

    def add(self, file_name: str):
        archive_name = build_archive_name(file_name, self.src_dir)
        if '/' in archive_name:
            self.check_dirs(archive_name)
        self.entries.add(file_name)

    def build(self):
        entries = list(self.entries)
        entries.sort()
        for file_name in entries:
            self.__write(file_name)


def check_args():
    target = None
    arg_it = iter(sys.argv[1::])
    for v in arg_it:
        if v == "-v":
            global verbose
            verbose = True
        elif target is None:
            target = v
        else:
            print(f"Invalid command line argument: {v}", file=sys.stderr)
            exit(2)
    if target is None:
        print("Please supply target zip file name.", file=sys.stderr)
        exit(2)
    if "ACTIVE_PROFILES" in os.environ:
        load_all_lazy()
    return target


def ensure_parent_exists(file_name: str):
    """
    For the given absolute file name, ensure the parent folder for the file exists.
    :param file_name: the fully-qualified file name.
    """
    parent = os.path.split(file_name)[0]
    if parent is not None and len(parent) > 0 and not os.path.isdir(parent):
        os.makedirs(parent)


def __find_root_dir(path: str):
    check_path = path
    while True:
        file_name = os.path.join(check_path, ".git")
        if os.path.isdir(file_name):
            return check_path + os.sep
        check_path, child = os.path.split(check_path)
        if len(child) == 0:
            break
    raise EnvironmentError(f"Unable to find .git in {path}.")


def add_json_resources(zip: MyZipper):
    for root, dirs, files in os.walk(src_name):
        for file in files:
            if not file.endswith(".json"):
                continue
            full_path = os.path.join(root, file)
            name = os.path.relpath(full_path, src_name)
            if verbose:
                print(f"{full_path} => {name} ...")
            zip.add(full_path)


def zip_python_files(source_module: ModuleType,
                     target_file: str):
    modules_done = set()
    root_dir = __find_root_dir(os.path.split(source_module.__file__)[0])

    def module_map(m: Any) -> Optional[ModuleType]:
        t = type(m)
        if t is not ModuleType:
            if hasattr(m, "__module__"):
                m = m.__module__
                return module_map(m)
            return None

        file_name = m.__dict__.get('__file__')
        if file_name is None or not file_name.startswith(root_dir):
            return None
        if type(m) is ModuleType and hasattr(m, "__file__") and "python3" not in getattr(m, "__file__"):
            return m
        else:
            return None

    def collect_them(module_set: Set, module: ModuleType):
        if module in module_set:
            return
        module_set.add(module)
        values = list(filter(lambda v: v is not None, map(module_map, module.__dict__.values())))
        for value in values:
            collect_them(module_set, value)

    collect_them(modules_done, source_module)

    # For some reason we seem to miss the __init__.py files, so take another pass
    parent = os.path.split(source_module.__file__)[0] + "/"

    for v in sys.modules.values():
        if v not in modules_done and hasattr(v, "__file__"):
            f = v.__file__
            if f is not None and f.startswith(parent):
                modules_done.add(v)

    # for k, v in sys.modules.items():
    #     if hasattr(v, "__file__"):
    #         print(k, getattr(v, "__file__"))

    ensure_parent_exists(target_file)
    temp_name = target_file + ".temp"
    good = False
    try:
        with MyZipper(temp_name, src_name) as zip:
            for mod in modules_done:
                if mod.__dict__.get('_EXCLUDE_FROM_BUILD') is not None:
                    print(f"Skipping {mod.__file__}")
                    continue
                file_name = mod.__file__
                archive_name = os.path.relpath(file_name, src_name)
                if verbose:
                    print(f"{file_name} -> {archive_name} ...")

                zip.add(file_name)
            add_json_resources(zip)
            zip.build()

        good = True
        print(f"Saved {len(modules_done)} files to {target_file}.")
    finally:
        if not good:
            if os.path.isfile(temp_name):
                os.remove(temp_name)

    if os.path.isfile(target_file):
        os.remove(target_file)
    os.rename(temp_name, target_file)
    return target_file


def show_checksum(file_name: str):
    with open(file_name, "rb") as f:
        data = f.read()
        m = hashlib.sha256(data)
        print(f"Hash: {m.digest().hex()}")


zip_file = zip_python_files(app, check_args())
if verbose:
    show_checksum(zip_file)
