"""Shared test helper utilities."""
import os
import tempfile
import zipfile
from contextlib import contextmanager


IMS_XML_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "testcontent", "samples", "ims_xml"
)


@contextmanager
def create_zip_with_manifest(manifest_filename, *additional_files, extra_entries=None):
    """Create a temp zip with a manifest and optional additional files.

    Args:
        manifest_filename: XML file in IMS_XML_DIR to use as imsmanifest.xml
        *additional_files: additional files from IMS_XML_DIR to include
        extra_entries: dict of {arcname: content_string} for in-memory entries
    """
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip_path = temp_zip.name
    temp_zip.close()
    try:
        manifest_file = os.path.join(IMS_XML_DIR, manifest_filename)
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.write(manifest_file, "imsmanifest.xml")
            for additional_file in additional_files:
                zf.write(os.path.join(IMS_XML_DIR, additional_file), additional_file)
            if extra_entries:
                for arcname, content in extra_entries.items():
                    zf.writestr(arcname, content)
        yield temp_zip_path
    finally:
        try:
            os.remove(temp_zip_path)
        except (FileNotFoundError, OSError):
            pass
