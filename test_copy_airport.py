"""
Tests for the copy_airport function in src/dobd.py.

These tests build a fake source airport.zip and a fake target drive in temp
directories so they can run without the real U: drive or any physical media.

Run directly:  python test_copy_airport.py
"""
import os
import sys
import shutil
import tempfile
import zipfile

# Make the src directory importable.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "src"))

import dobd


def _make_source_zip(zip_dir):
    """Create a source airport.zip containing a couple of known files."""
    os.makedirs(zip_dir, exist_ok=True)
    source_zip = os.path.join(zip_dir, "airport.zip")
    with zipfile.ZipFile(source_zip, "w") as zf:
        zf.writestr("runways.dat", "RW01\nRW19\n")
        zf.writestr("sub/towers.dat", "TWR1\n")
    return source_zip


def _make_drive():
    """Create a fake drive root with an existing ARS\\data folder."""
    drive_root = tempfile.mkdtemp(prefix="dob_drive_")
    data_dir = os.path.join(drive_root, "ARS", "data")
    os.makedirs(data_dir)
    return drive_root, data_dir


def test_happy_path():
    """Zip is copied, extracted into airport/, and the copied zip is deleted."""
    tmp = tempfile.mkdtemp(prefix="dob_src_")
    drive_root, data_dir = _make_drive()
    try:
        source_zip = _make_source_zip(tmp)

        dobd.copy_airport(drive_root, source_zip=source_zip)

        airport_dir = os.path.join(data_dir, "airport")
        dest_zip = os.path.join(data_dir, "airport.zip")

        assert os.path.isdir(airport_dir), "airport folder was not created"
        assert not os.path.exists(dest_zip), "airport.zip should have been deleted"
        assert os.path.isfile(os.path.join(airport_dir, "runways.dat")), \
            "runways.dat missing from extracted contents"
        assert os.path.isfile(os.path.join(airport_dir, "sub", "towers.dat")), \
            "nested towers.dat missing from extracted contents"

        with open(os.path.join(airport_dir, "runways.dat")) as f:
            assert f.read() == "RW01\nRW19\n", "extracted content mismatch"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(drive_root, ignore_errors=True)
    print("PASS: test_happy_path")


def test_missing_source_is_safe():
    """A missing source zip must not raise and must not create anything."""
    drive_root, data_dir = _make_drive()
    try:
        missing = os.path.join(data_dir, "does_not_exist.zip")
        dobd.copy_airport(drive_root, source_zip=missing)

        assert not os.path.exists(os.path.join(data_dir, "airport")), \
            "airport folder should not be created when source is missing"
        assert not os.path.exists(os.path.join(data_dir, "airport.zip")), \
            "no zip should be left behind when source is missing"
    finally:
        shutil.rmtree(drive_root, ignore_errors=True)
    print("PASS: test_missing_source_is_safe")


def test_missing_data_dir_is_safe():
    """A missing ARS\\data folder must not raise and must not copy the zip."""
    tmp = tempfile.mkdtemp(prefix="dob_src_")
    drive_root = tempfile.mkdtemp(prefix="dob_drive_")  # no ARS\data created
    try:
        source_zip = _make_source_zip(tmp)
        dobd.copy_airport(drive_root, source_zip=source_zip)

        assert not os.path.exists(os.path.join(drive_root, "ARS", "data", "airport.zip")), \
            "zip should not be copied when data dir is missing"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(drive_root, ignore_errors=True)
    print("PASS: test_missing_data_dir_is_safe")


def test_called_between_region_copy_and_matchfiles():
    """copy_airport must run after copy_region_files and before matchFiles in process_drive."""
    import inspect
    src = inspect.getsource(dobd.process_drive)
    i_region = src.index("copy_region_files(")
    i_airport = src.index("copy_airport(")
    i_match = src.index("matchFiles(")
    assert i_region < i_airport < i_match, \
        "copy_airport must be called after copy_region_files and before matchFiles"
    print("PASS: test_called_between_region_copy_and_matchfiles")


if __name__ == "__main__":
    test_happy_path()
    test_missing_source_is_safe()
    test_missing_data_dir_is_safe()
    test_called_between_region_copy_and_matchfiles()
    print("\nAll copy_airport tests passed.")
