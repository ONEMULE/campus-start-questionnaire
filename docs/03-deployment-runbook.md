# 03 / 杭州 VPS + server 双机部署手册

本手册的命令必须在完成只读核查与授权后执行。示例目录不是对现有环境的承诺。新站独立子域名根路径；不能不改代码就挂到已有站点子路径。

## 1. 拓扑与两端职责

杭州 VPS：DNS指向的公网入口、80/443、TLS、Nginx、请求限流、备用维护页。server：专用账户、Python运行时、应用、数据库、备份。公网请求经HTTPS到杭州，杭州仅通过Tailscale向server指定端口转发。数据库不走网络文件挂载，不暴露数据库服务。

应用使用 `X-Edge-Token` 校验代理入口；密钥仅在server的环境文件和杭州的私有proxy片段中。它是额外防护，不替代tailnet最小授权。`--forwarded-allow-ips` 仅填写杭州的当前Tailscale IP，不接受任意代理声明。

## 2. 先本地、再staging

在干净工作目录校验包的manifest。按README创建独立venv，安装依赖，运行 `pytest -q`。依赖来自常规Python包源；完全离线服务器须先在相同Python/架构/平台构建wheel目录，流程见开发文档。

staging使用独立域名、专用子目录、端口、环境文件、用户、数据库与密钥，示例为 `site_id=campus-start-staging`、`app_port=18090`、目录尾部`/staging`。只使用虚构学生数据。不可把生产库复制到staging“方便测试”。

## 3. 生成候选配置

复制模板到私有JSON，填写全部核验字段。账号已经存在时，`approved_uid/gid` 必须和 `id` 输出一致；账号尚未建立时，先走批准流程。生成器只验证和生成，不创建账号，不改系统。

```bash
umask 077
mkdir -p private
cp config/deployment.example.json private/deployment.json
# 在本地编辑私有文件，然后：
python scripts/render_deploy.py --config private/deployment.json --output private/candidate-prod --new-install
```

生成的文件有：本站systemd服务、备份service/timer、Nginx vhost、上游proxy片段、HTTP ACME引导片段、最小grant示例、logrotate、维护页、app.env、私有首次口令、非秘密部署摘要。

已有数据的更新不得用 `--new-install`。必须使用 `--reuse-env` 保留加密密钥、HMAC索引密钥、EDGE_TOKEN和口令哈希。不要通过“删数据库重装”解决密钥错误。

## 4. server：建立隔离目录和运行环境

下面的变量需由agent从已核验配置中赋值；示例不提供可误用的root密码、固定UID或真实IP。

```text
APP_ROOT=<批准的本站目录>
RELEASE=<APP_ROOT>/releases/1.1.0
RUN_USER=<批准的专用账户>
RUN_GROUP=<批准的专用组>
ENV_FILE=<批准的私有环境文件>
```

先核验父目录的遍历/读取权限和本地文件系统。创建APP_ROOT、releases、data、backups；data/backups仅专用账户可读写。不要把父科研目录整体chown给web账户。独立UID/GID需要新建时，给出明确的`groupadd/useradd`变更计划，由管理员按实际系统批准后执行。

将本包代码复制到RELEASE（排除`.env`、`private/`、运行数据库、缓存及任何真实导出）。由专用账户在该RELEASE下创建venv并安装依赖：

```bash
python3 -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/python" -m pip install -r "$RELEASE/requirements.txt"
```

更严格的复现可使用 `requirements.lock.txt`，其适用范围是记录的测试运行环境；不适配时必须记录目标平台重新解析的版本并复测，不静默升级。每个release自带venv，切回旧release时同时切回旧依赖。

首次安装建立 `APP_ROOT/current -> RELEASE`。后续更新用临时软链接加原子替换，而不是原地覆盖运行代码：

```bash
ln -s "$RELEASE" "$APP_ROOT/current.next"
mv -Tf "$APP_ROOT/current.next" "$APP_ROOT/current"
```

`current.next`必须不存在；此操作只针对已核验的本站目录。不要通过宽泛的`rm -rf`清理路径。

安装环境文件至ENV_FILE，权限0600，所有者为专用应用用户；它的父目录应允许该用户按需遍历但不让普通用户读取其他环境。安装渲染好的service至 `/etc/systemd/system/<site_id>.service`。服务的ExecStart指向 `APP_ROOT/current/.venv/bin/python`，只绑定server的已核验Tailscale IPv4和应用端口。

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now campus-start-prod.service
sudo systemctl status campus-start-prod.service --no-pager
```

服务名必须换成实际site_id。检查只读文件权限、日志、端口监听；不要为解决权限问题关闭SELinux。SELinux阻断时先依据审计日志，由管理员制定本站最小标签或策略，不执行全局disable。

默认 `DATABASE_JOURNAL_MODE=DELETE`。旧系统SQLite可以先安全使用默认模式；需要WAL时见运维文档，不能直接绕过版本门槛。

## 5. Tailscale：只授权杭州到应用端口

先验证双方当前地址和peer状态，再审核渲染的 `*.grant.json`。它是要合并的**一条授权片段**，不是完整tailnet策略。

Tailscale授权是叠加的：加入一条窄规则不会撤销旧的allow-all。如果当前已有广泛授权，必须确认实际暴露面。对既有政策的收窄可能影响其他服务，不得自动全量覆盖；在获批准的专用标签/策略或主机防火墙中进一步限制此端口。

安全验收至少包括：杭州可以访问server应用端口；未授权节点无法访问业务接口；没有EDGE_TOKEN时业务返回403；本地非Tailscale接口没有同端口监听。`/healthz`故意无需入口token，但仍受网络边界保护且只返回状态/版本。

不要执行 `tailscale up --reset`，不要改DERP、peer-relay、exit-node、校园路由。应用部署不需要把server变成出口节点，也不要求学生安装Tailscale。

## 6. 杭州：新增域名与HTTPS，不覆盖原站

先备份将要改动的本站相关文件，备份目录0700，含secret片段0600。确认现有Nginx的include规则、站点冲突、证书方法和80/443安全组；只新增授权子域名A记录到杭州公网地址。

有现成覆盖本域名的证书时，复用经批准的实际证书路径。没有证书时：

1. 安装本站 `*.bootstrap.conf` 到现有`http`上下文包含的专属站点位置，只提供HTTP ACME路径；确保同server_name没有冲突。
2. `nginx -t` 成功再reload。使用现有Certbot/ACME客户端，以核验后的webroot申请这个子域名。不得为了省事让安装器接管所有Nginx站点。
3. 例如现有系统确实使用Certbot时：

```bash
sudo certbot certonly --webroot -w "$ACME_WEBROOT" -d "$DOMAIN"
```

证书目录与 `tls_fullchain/tls_private_key` 对上之后重新渲染候选配置。确认真实续期timer和必要的renewal deploy hook；不要仅凭“certonly成功”宣称续期配置完成。
4. 用最终vhost替换本站bootstrap文件；不要同时启用同域名的两个80server块。

将 `*.proxy.conf` 安装到指定NGINX_INCLUDE_DIR，root0600；Nginx master需要能读取，普通用户不能读取。把维护页放到EDGE_STATIC_DIR，允许Nginx读取，但不要把整个候选目录暴露出去。最终vhost安装到已核验的include位置；它不是主`nginx.conf`。

```bash
sudo nginx -t
sudo systemctl reload nginx
```

禁止直接restart导致其他站点不必要中断。若语法测试失败，停止并修正本站候选片段，不清空原配置。

## 7. 分层验收

server就地或杭州跨tailnet健康检查，可以使用秘密文件读取入口token，而不把token写进命令行或shell历史：

```bash
python scripts/healthcheck.py --url "http://$NODE_TAILSCALE_IP:$APP_PORT" --env-file "$ENV_FILE"
```

这需要在**能够安全读取ENV_FILE的授权主机/账户**执行；不要为探测把server整个环境文件复制到杭州。杭州侧可由agent在内存中安全读取自身proxy密钥进行探测，并禁止打印该header。普通curl只测试 `/healthz` 不能证明业务鉴权和提交都正常。

公网检查：

```bash
python scripts/healthcheck.py --url "https://$DOMAIN"
```

再验证HTTP跳HTTPS、证书链、`/api/config`中的最终public_url、真实姓名/学号登记、完成提交、后台精确查询、无邀请意愿时不出现招募授权、导出前导零不丢失。

## 8. 正式二维码

最终 `PUBLIC_URL=https://<实际域名>` 确定并验证后，打开 `/qr`；保存 `/qr.png`。二维码编码固定站点入口，不受Host或query参数注入，不带学生ID、恢复码、后台密码或内部IP。

微信真机依次测试：扫一扫→打开→登记→完整作答→回执→后台查询。至少测试一次Android微信、一次iOS微信，分别覆盖校园Wi-Fi与手机流量。若出现风险提示、打不开或缓存旧版，排查域名信誉、TLS、DNS、真实网络与网站规则；不要用绕过警告的方法要求学生访问。

## 9. 备份定时器、日志与监控

安装渲染的 `<site>-backup.service/.timer`，确认backup目录权限。启用后手动执行一次，检查生成数据库备份、校验摘要、最新删除清单；做一次隔离恢复测试后再收真实数据。

```bash
sudo systemctl enable --now campus-start-prod-backup.timer
sudo systemctl start campus-start-prod-backup.service
sudo systemctl list-timers --all --no-pager
```

渲染的logrotate仅针对本站日志；是否安装到现有全局logrotate目录需先核验本机策略。应用不输出请求正文；Nginx最小access日志不记录查询串或原始客户端IP，但error日志可能带客户端信息，仍需权限与保留控制。

健康检查接入现有监控系统。单机+校园链路不是高可用；server停机或tailnet断开会显示杭州维护页，不会伪装成提交成功。

## 10. 发布、更新与回滚

发布前记录：当前软链接、代码manifest、私有环境文件版本、数据库备份及checksum、Nginx本站片段备份。新release独立建venv并通过测试；保留旧release。仅在维护窗口停止本站服务，切换current后启动；验收失败则切回旧release并启动。

数据库schema当前为1，没有破坏性迁移脚本。只换同schema代码时不回滚数据库，避免丢失新提交。若未来版本更改schema，必须提供单独备份、迁移和回退设计，不能凭“切回代码”保证数据兼容。

环境密钥绝不随release切换重新生成。真正恢复DB时先停止所有写入者和备份timer，按运维文档带最新删除清单恢复，再恢复定时器。自动化任务不能擅自覆盖新入库的数据。