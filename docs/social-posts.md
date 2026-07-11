# 发布帖文案

---

## V2EX 版

```markdown
[分享] 我写了个视频下载机器人，支持 Telegram / Rocket.Chat 双通道 + NAS 自动同步

写了个基于 yt-dlp 的下载机器人，核心逻辑就一句话：

**发链接 → 自动下载 → 实时进度推送 → WebDAV 同步 NAS → 次日自动清理**

主要特点：

1. 双 IM 引擎：Telegram 和 Rocket.Chat 可以同时跑，也可以二选一
2. 不用 SSH：给 bot 发链接就行，实时进度给你推到聊天里
3. NAS 友好：自动 755 权限 + 一键 WebDAV 服务，极空间/群晖直接拉
4. 每日清理：凌晨 3 点自动删 24h 前的文件，不占 VPS 磁盘
5. 安装简单：一行命令搞定，`bash install.sh --systemd -y`
6. 支持站点：YouTube/B站/PornHub/Twitter 等上千个（yt-dlp 原生）

项目地址：
https://github.com/akriamail/yt-dlp-telegram-bot

欢迎 star 和 PR 👏
```

---

## Telegram 中文圈版

```markdown
🎬 yt-dlp 视频下载机器人

给 TG 或 RC 发个链接，bot 自动下好视频，同步到你的 NAS。

• 支持 Telegram + Rocket.Chat 双通道
• 发送链接 → 自动下载 → 实时进度推送
• WebDAV 一键同步群晖/极空间
• 每日凌晨自动清理，不占磁盘
• 一行命令部署，自带 systemd

👉 https://github.com/akriamail/yt-dlp-telegram-bot

#自建 #NAS #yt-dlp #Telegram #RocketChat
```

---

## Linux.do 版

```markdown
# [开源] yt-dlp 视频下载 bot — TG/RC 双通道 + NAS 自动同步

写了一个基于 yt-dlp 的视频下载机器人，支持 Telegram 和 Rocket.Chat 双通道。

工作流：
1. 给 bot 发视频链接
2. yt-dlp 自动下载，实时进度推送到聊天
3. NAS 通过 WebDAV 拉走文件
4. 次日凌晨自动清理

部署很简单：
```bash
bash install.sh --systemd -y
```

支持所有 yt-dlp 能下的站点（YouTube/B站/Twitter/PornHub 等上千个）。

GitHub: https://github.com/akriamail/yt-dlp-telegram-bot
```
