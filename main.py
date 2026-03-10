import os
import sys
import traceback


def _write_crash(error_text):
    """Try to write crash log to multiple locations for accessibility."""
    locations = [
        # Android app-specific external storage (accessible from file manager)
        "/sdcard/Android/data/com.avsearcher.avsearcher/files",
        # Android external storage root
        "/sdcard",
        # Current working directory (p4a sets this to app files dir)
        os.getcwd(),
        # Next to this script
        os.path.dirname(os.path.abspath(__file__)),
    ]
    for loc in locations:
        try:
            os.makedirs(loc, exist_ok=True)
            path = os.path.join(loc, "avsearcher_crash.log")
            with open(path, "w") as f:
                f.write("Python: %s\n" % sys.version)
                f.write("Platform: %s\n" % sys.platform)
                f.write("CWD: %s\n" % os.getcwd())
                f.write("Env ANDROID_ARGUMENT: %s\n" % os.environ.get("ANDROID_ARGUMENT", "NOT SET"))
                f.write("\n")
                f.write(error_text)
            return
        except Exception:
            continue


def main():
    try:
        from avsearcher.native_app import run
        run()
    except Exception:
        error = traceback.format_exc()
        _write_crash(error)
        raise


if __name__ == "__main__":
    main()

