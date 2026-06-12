# IPTV M3U Updater

每日自动更新 IPTV 直播源 M3U。

## 使用方法

1. 把 M3U 源地址逐行写入 `sources.txt`。
2. GitHub Actions 会每天自动运行 `update_m3u.py`。
3. 合并去重后的播放列表会输出到 `output/index.m3u`。

## APTV 订阅地址

上传到 GitHub 后，APTV 使用这个格式：

```text
https://raw.githubusercontent.com/<你的GitHub用户名>/<仓库名>/main/output/index.m3u
```

如果默认分支是 `master`，把链接里的 `main` 改成 `master`。
