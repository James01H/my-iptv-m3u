# my-iptv-m3u

自动更新 IPTV 直播源 M3U。

## 使用方法

1. 把 M3U 源地址逐行写入 `sources.txt`。
2. GitHub Actions 会每 4 小时自动运行 `update_m3u.py`。
3. 脚本会合并、去重、检测可用性，并按频道名和响应速度排序。
4. 合并去重后的播放列表会输出到 `output/index.m3u`。

## 规则

- `Gather.m3u` 和 `Migu.m3u` 会全量纳入候选。
- 其他源只保留 CCTV、各地卫视、咪咕相关频道。
- `manual_channels.m3u` 可手工添加确认可播放的单条直播地址。

## APTV 订阅地址

APTV 使用这个订阅地址：

```text
https://raw.githubusercontent.com/James01H/my-iptv-m3u/main/output/index.m3u
```
