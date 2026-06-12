# my-iptv-m3u

每日自动更新 IPTV 直播源 M3U。

## 使用方法

1. 把 M3U 源地址逐行写入 `sources.txt`。
2. GitHub Actions 会每天自动运行 `update_m3u.py`。
3. 合并去重后的播放列表会输出到 `output/index.m3u`。

## APTV 订阅地址

APTV 使用这个订阅地址：

```text
https://raw.githubusercontent.com/James01H/my-iptv-m3u/main/output/index.m3u
```
