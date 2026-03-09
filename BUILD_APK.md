# AVSearcher APK 构建指南（Windows 专用，不需要 WSL）

## 方法一：GitHub Actions（推荐，全自动）

只需把代码推送到 GitHub，APK 自动构建完成后下载即可。

### 操作步骤：

1. **在 GitHub 上创建新仓库**
   - 去 https://github.com/new 创建一个新仓库（名字随意，比如 `avsearcher`）
   - 选 Private（私有）或 Public（公开），**不要**勾选 README

2. **双击运行 `push_and_build_apk.bat`**
   - 会自动初始化 Git 仓库，提交代码，推送到 GitHub
   - 首次运行会要求输入 GitHub 仓库地址

3. **下载 APK**
   - 打开你的 GitHub 仓库页面
   - 点击顶部 **Actions** 选项卡
   - 点击最新一次运行
   - 滚动到底部，找到 **AVSearcher-APK**，点击下载

⏱ 首次构建约 20-40 分钟，后续构建有缓存约 10 分钟。

---

## 方法二：Google Colab（免费，无需 GitHub 账号）

用谷歌的免费服务器构建，只需要浏览器。

### 操作步骤：

1. **双击运行 `pack_for_colab.bat`**
   - 会在项目目录生成 `avsearcher_project.tar.gz`

2. **打开 [Google Colab](https://colab.research.google.com/)，新建笔记本**

3. **第一个单元格** — 上传并解压项目：
```python
from google.colab import files
uploaded = files.upload()  # 选择 avsearcher_project.tar.gz
!tar -xzf avsearcher_project.tar.gz
%cd avsearcher_project
```

4. **第二个单元格** — 安装依赖并构建APK：
```python
!pip install -q buildozer==1.5.0 cython==0.29.36
!sudo apt-get update -qq
!sudo apt-get install -y -qq openjdk-17-jdk autoconf libtool pkg-config \
    libffi-dev libssl-dev zlib1g-dev cmake ccache zip unzip
!yes | buildozer -v android debug
```

5. **第三个单元格** — 下载APK：
```python
import glob
apks = glob.glob('bin/*.apk')
if apks:
    files.download(apks[0])
else:
    print("构建失败，请检查上方日志")
```

⏱ 约 15-30 分钟完成。

---

## 方法三：Docker Desktop（本地构建）

需要安装并启动 Docker Desktop。

1. 启动 Docker Desktop
2. 双击运行 `build_apk_docker.bat`
3. APK 输出至 `bin/` 目录
