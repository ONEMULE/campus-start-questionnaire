# 02 / 基础设施输入与证据状态

## 已知事实和不能猜的事实

用户已拥有域名，并希望结合 server 与杭州 VPS 发布。实机地址、端口和 DNS 参数属于私有部署资料，不写入代码仓库；部署前必须在授权环境中重新核验，不能把历史中继端口当作应用端口。

`/data/lx/campus-start/prod` 是一个建议的隔离子目录，不是对现有目录所有权、磁盘配额、SELinux标签和用户授权的断言。最终主机名、域名、证书、server tailnet地址和专用服务账号必须从当前环境核实。

## 唯一生产配置清单

复制 `config/deployment.example.json` 到私有位置，不要直接改为真实秘密后提交仓库。该文件本身不含应用密钥；密钥由配置生成器私下生成。

| 字段 | 由谁确定 / 如何确认 |
|---|---|
| `domain` | 用户授权的最终二级域名；确认未被其他站点占用，仅FQDN不带协议/路径 |
| `node_tailscale_ip` | 在实际server运行 `tailscale ip -4` 并核验主机身份 |
| `edge_tailscale_ip` | 在杭州VPS运行 `tailscale ip -4`，与当前tailnet资产一致 |
| `app_port` | 建议prod18080、staging18090；用 `ss -lntp` 确认不冲突 |
| `run_user/run_group` | 经批准的独立低权限服务账号，不使用root或默认研究账号 |
| `approved_uid/approved_gid` | 读取现有账号或事先批准未占用值；生成器不自动新建账号 |
| `app_root` | 专属应用子目录；本地文件系统，有实际权限与容量，不共用科研输出目录 |
| `environment_file` | 例 `/etc/campus-start/prod.env`；只允许应用用户/管理员读 |
| `nginx_include_dir` | 现有 Nginx 允许引入的片段目录，不假设发行版统一布局 |
| `edge_static_dir` | 杭州维护页独立目录，不放身份数据或密钥 |
| `acme_webroot` | 现有证书续期所用真实webroot，或批准的新路径 |
| `tls_fullchain/tls_private_key` | 实际覆盖本域名的证书链/私钥路径；只核验路径和域名覆盖，不输出私钥 |
| `operator_name/privacy_contact` | 真实负责本次数据处理的单位或负责人及可用联系渠道；用户确认 |
| `cohort` | 默认2026；同一学号在同一届次内唯一 |
| `student_id_pattern` | 默认6–16位数字，不代表本校实际格式；依据授权名册/规则收紧 |
| `roster_required` | 是否启用授权名册字段匹配；启用前必须先导入、测试再开放登记 |
| `require_enrollment_code` | 可选参与口令；不是身份认证，不能代替同意或学校SSO |
| `retention_days/draft_retention_days` | 例90/7天；真实目的和保留周期由数据负责人批准 |
| `admin_allowlist` | 推荐可信管理出口CIDR；以杭州看到的真实客户端源地址为准 |
| `allow_public_admin` | 无固定管理出口时，必须显式批准true才渲染；仍有HTTPS口令/会话/CSRF保护 |
| `icp_number/police_number/police_url` | 按真实备案与业务主体核对，未完成不得捏造；前端只展示真实填写值 |

不要将 `domain` 直接设置成已有主页域名来替换站点；优先申请或选择已授权的独立子域名。DNS A 记录指向杭州公网IPv4，不是100.x Tailscale地址，也不是server的校园私网地址。没有完整验证IPv6访问链路前不要新增AAAA记录。

## 只读勘查建议

两端分别执行 `sh scripts/preflight.sh`，再补充：

```bash
hostname -f
id
python3 -c 'import sys,sqlite3; print(sys.version); print(sqlite3.sqlite_version)'
ss -lntp
findmnt -T /data/lx
getfacl -p /data/lx
getent passwd
getent group
tailscale ip -4
tailscale status
systemctl status tailscaled --no-pager
nginx -v
nginx -t
systemctl list-timers --all --no-pager
getenforce
```

没有某条命令不代表要立即全局安装软件。账号列表、tailnet拓扑和服务状态只用于本地核查，给用户的总结要去除无关人员、设备与秘密。TLS续期、现有Nginx片段、服务用户和文件标签优先精准读取，不把 `nginx -T` 全文复制到聊天。

## 环境记录模板

每项填写 `VERIFIED / PARTIAL / NEED_INPUT / BLOCKED`，附验证时间、主机和最小必要证据。

```text
最终二级域名：NEED_INPUT
杭州公网IP与DNS记录：NEED_INPUT
杭州Tailscale IPv4：不在代码仓库中记录，待实机复核
server主机与Tailscale IPv4：NEED_INPUT
两端TCP连通、实际有效tailnet策略：NEED_INPUT
prod/staging端口：待占用检查
prod/staging独立UID/GID：待批准与核验
专属本地磁盘/配额/ACL/SELinux：NEED_INPUT
TLS证书覆盖、webroot、续期timer：NEED_INPUT
Nginx新增vhost不会影响原站：NEED_INPUT
备案及活动主体/数据处理权限：待负责人确认
授权名册和真实学号格式：待负责人确认
备份位置、异地策略、删除清单保管：NEED_INPUT
```

历史“已备案”“网络曾连通”等描述不能代替本次站点、主体、域名、网络规则和活动数据用途的实际复核。没有确认的项保留为发布阻断，不悄悄填猜测值。
