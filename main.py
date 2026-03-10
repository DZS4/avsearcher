import os
import sys
import traceback


def main():
    try:
        from avsearcher.native_app import run
        run()
    except Exception:
        # Android 闪退时把错误写到文件方便排查
        try:
            err_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash")
            os.makedirs(err_dir, exist_ok=True)
            with open(os.path.join(err_dir, "crash.log"), "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()

