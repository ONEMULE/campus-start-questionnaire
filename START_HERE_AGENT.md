# Agent 从这里开始

## 任务

把《大一，启动！》部署成面向海洋学院新生的手机网页。用户已拥有域名；目标是由杭州 VPS 提供公网 HTTPS 入口，server 承载应用和本地数据库。不得把当前资源包误认为已经上线的网站。

正式参与必须登记姓名与学号。姓名/学号只用于活动登记、区分记录和经允许的联系，不进入游戏分数。邀请意愿另行选择。保留现有52节点题库与单局32节点，不临时删成普通问卷。

## 按顺序阅读

`AGENTS.md` → `docs/01-scope-and-status.md` → `docs/02-infrastructure-inputs.md` → `docs/03-deployment-runbook.md` → `docs/04-data-security-privacy.md` → `docs/06-operations.md` → `docs/07-acceptance.md`。

代码真值以本包 `backend/engine.py`、`content/questions.v1.json` 和测试为准。`reference/original-design-v1.0.docx` 是历史构想，不能把其中互相矛盾的计分、旧地址或隐私描述覆盖回新实现。

## 第一次行动只能是只读勘查

检查两台机器的真实身份、当前 tailnet 地址、系统、可用 Python、端口占用、Nginx include 布局、现有 TLS 更新方式、专属目录磁盘与 ACL、SELinux、授权 UID/GID。可用 `scripts/preflight.sh`，但先读脚本。不要抓取并输出完整 `.env`、证书私钥、SSH 密钥或含上游秘密的整份 Nginx 配置。

历史现场地址不写入代码仓库；部署 agent 必须从获得授权的环境中重新核验杭州 VPS 与 server 的 Tailscale 地址、监听端口和最终二级域名，不得使用聊天记录中的旧参数。

先把能够从授权环境自行确认的信息补齐，不要把一长串本可自动读取的参数再全部问用户。只有数据负责人、最终域名选择、现有站点变更授权、身份名册使用权限等无法从只读证据确定的事项才需要用户确认。

## 输出部署前计划

交付私有环境清单、拟增改文件列表、两个端口/两个账户（若同时建 staging 与 prod）、TLS复用或新申请方案、Tailscale最小授权差异、备份位置、测试方法和回滚点。账户 UID/GID 必须是获批准且未占用的值，不要生成一个看似合理的固定 UID。

候选配置生成命令：

```bash
python scripts/render_deploy.py --config private/deployment.json --output private/candidate-prod --new-install
```

升级已有数据库时必须改用：

```bash
python scripts/render_deploy.py --config private/deployment.json --output private/candidate-upgrade --reuse-env /etc/campus-start/prod.env
```

生成器不会安装、重启或改动任何系统配置。`app.env`、`*.proxy.conf` 和首次口令文件属于秘密文件，不发聊天、不提交仓库、不放公网静态目录。

## 上线前必须成立

所有单元/API测试通过；两个端点健康；HTTPS证书和DNS正确；server应用只绑定指定Tailscale地址；其他未授权节点无法调用业务接口；实际授权边界经过验证；强管理员口令；生产匿名测试入口关闭；数据负责人/联系方式真实；数据库及备份在本地专属目录；备份能恢复且撤回记录不会复活；真实微信完整作答后后台能查到同一姓名和学号。

如果系统SQLite是未修复WAL问题的旧版本，保持默认 `DATABASE_JOURNAL_MODE=DELETE`；不要全局升级科研环境或强制打开WAL。需要WAL时，单独评估固定运行时，仍不得覆盖系统Python。

## 最终交付给用户

填写 `docs/09-agent-delivery-template.md`：正式URL、二维码地址和图片、后台URL、服务名、安装目录、代码版本、测试证据、备份/保留期限、管理员凭证的私密交付方式、回滚命令、剩余限制。不要在完成回执里附明文口令。
