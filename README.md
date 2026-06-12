# my-iptv-m3u

自动更新 IPTV 直播源 M3U。

## 使用方法

1. 把 M3U 源地址逐行写入 `sources.txt`。
2. GitHub Actions 会每 4 小时自动运行 `update_m3u.py`。
3. 脚本会合并、去重，并保留上游原始播放参数。
4. 合并去重后的播放列表会输出到 `output/index.m3u`。

## 规则

- `Gather.m3u` 和 `Migu.m3u` 会全量纳入候选。
- 其他源只保留 CCTV、各地卫视、咪咕相关频道。
- `manual_channels.m3u` 可手工添加确认可播放的单条直播地址。
- 默认不启用 GitHub 服务器测速，避免云端网络可用但本地 APTV 不可用的误判。
- 如确实需要测速，可在 Actions 里设置环境变量 `CHECK_STREAMS=1`。

## APTV 订阅地址

APTV 使用这个订阅地址：

```text
https://raw.githubusercontent.com/James01H/my-iptv-m3u/main/output/index.m3u
```

## 手工整理列表

咪咕和 CCTV 整理列表：

```text
https://raw.githubusercontent.com/James01H/my-iptv-m3u/main/整理后的直播链接/频道对应链接.m3u
```

频道与链接对照：

```text
https://raw.githubusercontent.com/James01H/my-iptv-m3u/main/整理后的直播链接/频道对应链接.md
```

## CCTV 精简稳定版

只看 CCTV 建议使用这个：

```text
https://raw.githubusercontent.com/James01H/my-iptv-m3u/main/cctv/cctv-stable.m3u
```
