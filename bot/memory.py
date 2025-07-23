import os
import glob
import pickle
from datetime import datetime
from filelock import FileLock, Timeout

memory_directory_name = "working_memory"

def get_pathname(filename):
    return os.path.join(memory_directory_name, filename)

def get_lock_path(pathname):
    return f"{pathname}.lock"

# Load data or return None
def load(filename):
    pathname = get_pathname(filename)
    lock_path = get_lock_path(pathname)
    lock = FileLock(lock_path, timeout=5)
    try:
        with lock:
            if os.path.exists(pathname):
                with open(pathname, "rb") as f:
                    return pickle.load(f)
            else:
                return None
    except Timeout:
        print(f"Timeout while trying to load {filename}")
        return None

# Save data
def save(data, filename):
    pathname = get_pathname(filename)
    lock_path = get_lock_path(pathname)
    lock = FileLock(lock_path, timeout=5)
    if not os.path.exists(memory_directory_name):
        os.makedirs(memory_directory_name)
    try:
        with lock:
            with open(pathname, "wb") as f:
                pickle.dump(data, f)
    except Timeout:
        print(f"Timeout while trying to save {filename}")

# Sync object with memory
def sync_object(data, filename):
    loaded_data = load(filename)
    try:
        if loaded_data is None or loaded_data["timestamp"] < datetime.now():
            newest_data = data
        else:
            newest_data = loaded_data["data"]
    except Exception as e:
        print(f"Error during loading object for syncing: {e}")
        newest_data = data
    data = newest_data
    save({"timestamp": datetime.now(), "data": newest_data}, filename)
    return newest_data

# Load object and refresh timestamp
def load_object(filename, default_value=None):
    loaded_data = load(filename)
    try:
        got_data = default_value if loaded_data is None else loaded_data["data"]
    except Exception as e:
        print(f"Error during loading object: {e}")
        got_data = default_value
    save({"timestamp": datetime.now(), "data": got_data}, filename)
    return got_data

# Remove all .lock files
def remove_all_filelocks():
    lock_files = glob.glob(os.path.join(memory_directory_name, '*.lock'), recursive=True)
    for lock in lock_files:
        try:
            os.remove(lock)
        except Exception as e:
            print(f"Failed to delete lock file: {lock} - {e}")

# Clear all .pkl files in memory
def clear_memory():
    response_string = ""
    pkl_files = glob.glob(os.path.join(memory_directory_name, '*.pkl'), recursive=False)
    for file_path in pkl_files:
        lock_path = get_lock_path(file_path)
        lock = FileLock(lock_path, timeout=5)
        try:
            with lock:
                os.remove(file_path)
                response_string += f"Deleted: {file_path}\n"
        except Timeout:
            print(f"Timeout while deleting {file_path}")
            response_string += f"Timeout deleting: {file_path}\n"
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
            response_string += f"Error deleting: {file_path}\n"
    return response_string