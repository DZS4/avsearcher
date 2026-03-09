# AVSearcher

飞机杯评测查询软件，现已提供两种入口：

- 原生桌面 / Android UI：入口 [main.py](/home/aaaa/avsearcher/main.py)
- 旧版浏览器 API：入口 [server.py](/home/aaaa/avsearcher/server.py)

默认聚合两个中文垂直评测源，并已在 2026-03-09 实测可抓取：

- `新况味测评`：`https://www.xkwceping.com/fjb/feed/`
- `B酱评测`：`https://www.cup001.com/feed/`

## 原生运行

安装原生 UI 依赖：

```bash
python3 -m pip install --target .deps -r requirements-native.txt
```

启动原生界面：

```bash
./run_native.sh
```

如果不想用脚本：

```bash
PYTHONPATH=.deps KIVY_HOME=.kivy-home python3 main.py
```

## Windows EXE

桌面版已经改成原生 Kivy UI，不需要浏览器启动。

在 Windows 机器上执行：

```bat
build_windows_exe.bat
```

输出文件：

```text
dist\AVSearcher\AVSearcher.exe
```

注意：

- `PyInstaller` 不能在 Linux 上直接产出 Windows `exe`，需要在 Windows 上构建。
- 本仓库已经准备好了打包脚本和资源复制配置，当前这台 Linux 机器只能把工程准备好，不能直接给你产出 `exe`。

## Android APK

Android 打包配置已经写好，文件是 [buildozer.spec](/home/aaaa/avsearcher/buildozer.spec)。

在 Linux 机器上准备好 Java、Android SDK 和编译工具链后执行：

```bash
./build_android_apk.sh
```

常见产物位置：

```text
bin/*.apk
```

当前这台机器在 2026-03-09 的实际情况：

- Python: `3.8.10`
- Java: 未安装
- `ANDROID_HOME` / `ANDROID_SDK_ROOT`: 未设置

也就是说，`apk` 工程已经准备好，但这台机器现在还不具备直接出包条件。

## 浏览器版 API

如果还要保留 HTTP 接口：

```bash
python3 -m pip install --target .deps -r requirements-web.txt
python3 server.py
```

## 可扩展项

- 查询来源配置： [avsearcher/sources.json](/home/aaaa/avsearcher/avsearcher/sources.json)
- 原生 UI： [avsearcher/native_app.py](/home/aaaa/avsearcher/avsearcher/native_app.py)
- 查询核心： [avsearcher/search.py](/home/aaaa/avsearcher/avsearcher/search.py)

## 测试

```bash
python3 -m unittest discover -s tests
```
