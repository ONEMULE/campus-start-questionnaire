# 大一，启动！
## 海洋学院新生模拟器 · 开发与双机部署源码 v1.1.0-content.2

> 你的大学，没有统一攻略。

正式参与：登记姓名、学号并同意本次活动的数据说明 → 32个剧情节点 → 第一学年结局 → 服务器保存 → 工作人员后台查看与人工评阅。原来的“潮汐元年”仅保留在历史参考文件中，线上品牌已经更换。

**交给开发 agent：先读 `START_HERE_AGENT.md`，再按 `HANDOFF_PROMPT.md` 执行。** 本包没有连接、修改或部署任何真实线上服务器；生产配置必须用实机核验的信息生成。不要把“已有域名”理解为 DNS、证书、备案、数据处理权限都已完成。

## 这次真正提供的内容

| 内容 | 入口 |
|---|---|
| 手机优先的完整答题端 | `web/index.html`、`web/app.js`、`web/styles.css` |
| 姓名/学号登记、自动保存、恢复码、幂等提交、删除 | `backend/main.py` |
| 52个展开剧情节点、5条路线、单局32节点 | `content/questions.v1.json` |
| 服务端判路、15项策略指示、兴趣、12种结局规则、岗位线索 | `backend/engine.py` |
| 管理后台、学号精确查询、CSV、作品评阅、审计 | `web/admin.*`、`/api/admin/*` |
| 数据加密、管理员口令哈希、记录隔离 | `backend/security.py`、`backend/store.py` |
| 杭州入口 + server 应用的配置生成器 | `scripts/render_deploy.py`、`deploy/templates/` |
| 备份、到期清理、恢复、授权名册导入 | `scripts/ops.py` |
| 自动化测试、浏览器复测脚本 | `tests/` |
| 原始设计Word与旧版源码 | 不随代码仓库发布，留在原始开发资料的私有历史归档中 |

## 本地启动：只使用虚构数据

需要独立 Python 3.11+ 环境；本包实际测试解释器为 Python 3.13.5。其他版本必须在目标服务器复测。默认不用 Docker、不依赖 npm 构建、不依赖公网字体/CDN。

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/bootstrap_local.py --port 8000
python -m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8000
```

Windows PowerShell 将激活命令换为 `.\.venv\Scripts\Activate.ps1`。首次生成器会创建仅供本地使用的 `.env`，并显示一次随机管理员口令；已有 `.env` 时拒绝覆盖。

浏览器打开 `http://127.0.0.1:8000/`。后台 `/admin`，数据说明 `/privacy`，二维码 `/qr`。**本地二维码不能发给新生。** 本项目不是双击 HTML 即可运行的无后端页面：登记、提交、查询都依赖同源 API。

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

正式生产不要复制本地 `.env`，不要开放 Uvicorn 到 `0.0.0.0`，不要把开发测试数据库同步到线上。

## 推荐部署拓扑

```text
微信 / 手机浏览器
       |
       | HTTPS :443，独立二级域名
       v
杭州 VPS：现有 Nginx + 本站新增 vhost + TLS + 限流 + 维护页
       |
       | Tailscale 网络，限定源/目标/端口，额外 X-Edge-Token
       v
server：专用非 root 用户 + systemd + Python 应用
       |
       +-- 本地磁盘 SQLite（姓名、学号、原始答案、结果加密字段）
       +-- 私有备份和删除清单
```

公网不直接开放数据库或应用端口；不改变已有 DERP/peer-relay/exit-node、SSH、科研调度和其他站点。默认独立子域名根路径，不支持未经修改就挂到 `/freshman/` 子路径。

## 最短交接路径

1. agent 按 `docs/02-infrastructure-inputs.md` 做只读勘查，填 `config/deployment.example.json` 的私有副本。
2. 按 `docs/03-deployment-runbook.md` 生成候选配置，提交变更计划与回滚点，获得发布授权后分别安装到两端。
3. 跑测试和 HTTPS 健康检查；在真实微信、手机流量和校园 Wi-Fi 各完整作答一次，确认后台结果。
4. 最终 `PUBLIC_URL` 确定后，从 `/qr` 保存正式二维码，再公开发群。

## 重要边界

姓名与学号是活动登记字段，不参与分数，也不出现在分享文案。格式校验、重复检测和可选名册核对均**不等于学校统一身份认证**；本包未集成学校 SSO、短信验证码或微信实名。

行为规则是当前剧情的游戏策略映射，不是验证过的人格量表。后台不自动录取或淘汰，不因缺少作品或拒绝联络而给人扣资格分。完整能力判断仍需要自愿体验和人工观察。

照片题必须提供8张获授权的真实图片才能启用；默认仅提供文字开场、剪辑结构提案及跳过。没有 AI 自动审美打分、实际视频上传/剪辑器、真实微信端已测结论或生产负载保证。

SQLite 默认 `DELETE` 回滚日志模式。WAL 是可选项且带已修复版本门槛；不要为“提高并发”在未知版本上直接开启 WAL，详见运维文档。

## 文档导航

- `docs/01-scope-and-status.md`：已实现/未实现、旧版差异。
- `docs/02-infrastructure-inputs.md`：环境资料与证据状态。
- `docs/03-deployment-runbook.md`：两端部署、TLS、Tailscale、回滚。
- `docs/04-data-security-privacy.md`：数据结构、身份、授权、秘密管理。
- `docs/05-story-and-scoring.md`：题库、路线、规则与科学性边界。
- `docs/06-operations.md`：备份、到期清理、恢复、故障处理。
- `docs/07-acceptance.md`：发布检查、微信实测、性能验证。
- `docs/08-development-guide.md`：开发、接口、版本与素材。
- `docs/09-agent-delivery-template.md`：agent 最终发布回执。
- `docs/10-official-sources.md`：技术与数据保护的官方来源。
- `reports/TEST_REPORT.md`：本次实际测试范围。

版本和目录见 `VERSION.json`。不要将密钥、名册、真实数据、导出文件、生成报告或渲染后的秘密配置推入 Git 仓库。
