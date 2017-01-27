
import json
import os
from ricecooker import config
from cachecontrol.caches.file_cache import FileCache
from le_utils.constants import file_formats

old_cache = {}
new_cache = FileCache(config.FILECACHE_DIRECTORY, forever=True)

print("Opening file cache")
with open(os.path.join(config.RESTORE_DIRECTORY, "file_restore.json"), 'r') as jsonobj:
    old_cache = json.load(jsonobj)

print("Iterating over old keys")
for k,v in old_cache.items():
	filename = v['filename'] if 'filename' in v else v
	extension = os.path.splitext(filename)[1][1:]
	new_key = None
	if k.endswith(" (encoded)"):
		new_key = "ENCODED: {}".format(k.replace("(encoded)", "(base64 encoded)"))
	elif v.get('extracted'):
		if extension == file_formats.PNG:
			new_key = "EXTRACTED: {}".format(k.replace(" (extracted thumbnail)", ""))
		elif extension == file_formats.MP4:
			new_key = "COMPRESSED: {0} (default compression)".format(filename)
	else:
		new_key = "DOWNLOAD:{}".format(k)

	new_cache.set(new_key, bytes(filename, "utf-8"))
	print("--- Mapped {} to {}".format(new_key, filename))
print("DONE")
