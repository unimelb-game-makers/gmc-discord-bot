# Disk-backed store for discord event thumbnails, keyed by event name.
# Image bytes never sit in the store itself: they are written straight to disk
# on fetch and read back only for the single event being pushed to discord.

import hashlib
import os
import shutil

from bot.utils.memory import get_pathname

store_directory_name = "event_thumbnails"

# Discord rejects covers well above this; also bounds peak memory per image
max_image_bytes = 8 * 1024 * 1024


class ThumbnailStore:
    def __init__(self, legacy_filename=None):
        self.directory = get_pathname(store_directory_name)
        os.makedirs(self.directory, exist_ok=True)
        if legacy_filename is not None:
            self._discard_legacy(legacy_filename)

    # The old pickle held every thumbnail ever seen as raw bytes in one blob.
    # Thumbnails are re-fetched on every sync, so it is pure dead weight.
    def _discard_legacy(self, filename):
        for pathname in (get_pathname(filename), f"{get_pathname(filename)}.lock"):
            try:
                if os.path.exists(pathname):
                    os.remove(pathname)
            except Exception as e:
                print(f"Failed to remove legacy thumbnail cache {pathname}: {e}")

    def _path(self, key):
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(self.directory, f"{digest}.img")

    def __contains__(self, key):
        return os.path.exists(self._path(key))

    def __getitem__(self, key):
        pathname = self._path(key)
        if not os.path.exists(pathname):
            raise KeyError(key)
        with open(pathname, "rb") as f:
            return f.read()

    def __setitem__(self, key, image_bytes):
        pathname = self._path(key)
        temp_pathname = f"{pathname}.part"
        with open(temp_pathname, "wb") as f:
            f.write(image_bytes)
        os.replace(temp_pathname, pathname)

    def pop(self, key, default=None):
        pathname = self._path(key)
        try:
            os.remove(pathname)
        except FileNotFoundError:
            return default
        except Exception as e:
            print(f"Failed to remove thumbnail for {key}: {e}")
        return default

    def clear(self):
        try:
            shutil.rmtree(self.directory)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Failed to clear thumbnail store: {e}")
        os.makedirs(self.directory, exist_ok=True)

    # Drop thumbnails whose event is no longer known, so the store cannot grow
    # unbounded as events come and go
    def prune(self, keys):
        kept = {os.path.basename(self._path(key)) for key in keys}
        try:
            names = os.listdir(self.directory)
        except Exception as e:
            print(f"Failed to list thumbnail store: {e}")
            return
        for name in names:
            if name in kept:
                continue
            try:
                os.remove(os.path.join(self.directory, name))
            except Exception as e:
                print(f"Failed to prune thumbnail {name}: {e}")

    # Stream a thumbnail to disk. Returns True when the file is in place.
    def fetch(self, key, url, requests_module, timeout=10):
        pathname = self._path(key)
        temp_pathname = f"{pathname}.part"
        try:
            with requests_module.get(url, timeout=timeout, stream=True) as response:
                if response.status_code != 200:
                    return False
                written = 0
                with open(temp_pathname, "wb") as f:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        written += len(chunk)
                        if written > max_image_bytes:
                            raise ValueError(f"thumbnail exceeds {max_image_bytes} bytes")
                        f.write(chunk)
            os.replace(temp_pathname, pathname)
            return True
        except Exception as e:
            print(f"Error fetching image from URL: {e}")
            try:
                os.remove(temp_pathname)
            except OSError:
                pass
            return False
