# 家庭装修需求

供家人、设计师和施工方共用的手机优先装修事项清单。每条事项可记录房间、尺寸规范、参考图、补充说明和确认状态。

线上地址：<https://zhuangxiu.goodsport.fun>

## 目录

- `dist/index.html`：前端主文件，也是 Nginx 对外提供的页面。
- `outputs/家庭装修需求.html`：可直接打开的交付副本；打开本地文件时也会连接线上数据服务。
- `app/server.js`：仅监听本机的 Node API，负责事项读取、写入和图片上传。
- `app/db.py`：SQLite 数据读写与校验。
- `app/backup.sh`：数据库与图片归档脚本。
- `app/renovation-api.service`、`app/zhuangxiu.goodsport.fun.conf`：服务器部署配置样本。

## 数据边界

- 事项保存在服务器 SQLite，图片独立保存；浏览器 `localStorage` 仅作断网暂存。
- 不提交生产数据、上传图片、备份、手机截图、密钥或本机缓存。
- 保存成功应显示“已安全保存到服务器”；重要节点仍可通过“导出”下载或复制完整 JSON。

## 发布前检查

1. `node --check app/server.js`
2. 打开线上页面，新增或编辑一条测试事项后刷新页面，确认服务端读回。
3. 上传图片，确认缩略图、详情大图和全屏浏览均可访问。
4. 在服务器检查 `systemctl is-active renovation-api` 与 `nginx -t`。

## 版本规则

- `main`：已验证、可部署的版本。
- 功能调整使用 `feature/` 分支；修复使用 `fix/` 分支。
- 仅在可复现的功能点完成后提交；标签采用 `v主版本.次版本.修订号`。
