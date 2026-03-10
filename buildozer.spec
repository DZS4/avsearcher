[app]
title = AVSearcher
package.name = avsearcher
package.domain = com.avsearcher
source.dir = .
source.include_exts = py,json,txt,png,jpg,kv
source.exclude_dirs = tests,build,dist,bin,__pycache__,.git,.github
version = 1.1.0
requirements = python3,kivy==2.3.1,requests,charset_normalizer,idna,urllib3,certifi
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png

android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.arch = arm64-v8a

# 跳过不需要的主题颜色设定
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1

