# 06 / 运维、备份、清理和恢复

## 日常运行

systemd管理本站应用；默认1个Uvicorn worker、MemoryMax512M、CPUQuota100%、TasksMax128。它不是给科研服务器额外申请512核心，更不使用GPU或Slurm。上限是保护科研负载的起点，不是容量承诺。单worker仍可能有多线程数据库连接，不代表完全没有并发。

`/healthz`：进程存活和版本；`/readyz`：数据库可读、内容与规则版本。真正活动健康还需受控虚构账号的登记→提交→后台闭环；不要持续制造真实学生记录做探针。

出现502时先区分：应用未启动、Tailscale不通、端口监听错误、proxy_bind地址不正确、入口token不一致或TLS/vhost不对。不要用放开全部端口/禁用防火墙来“临时解决”。杭州维护页保留明确未提交提示。

## SQLite日志模式与2026修复

默认 `DATABASE_JOURNAL_MODE=DELETE`，使用回滚日志和本地文件系统，适合本次轻量单应用部署。Python实际链接的SQLite版本用以下命令查看，不以系统`sqlite3` CLI版本代替：

```bash
python -c 'import sqlite3; print(sqlite3.sqlite_version)'
```

SQLite官方披露WAL-reset竞争问题：旧版本WAL在多连接同时写入/检查点时可能损坏数据，已在3.51.3及特定回补版本修复。[sources第3项。]本应用允许WAL的版本门槛为≥3.51.3，或3.50分支≥3.50.7，或3.44分支≥3.44.6。不同发行商额外回补不能仅凭口头判断；本包不提供绕过开关。

不用WAL即可避免依赖该WAL特定场景。确实需要WAL时，只升级本项目独立运行环境、先在staging压测，再经批准停机切换。不要全局替换科研Python。已经存在的DB与配置模式不同时应用会停止，避免运行中自动切模式。

WAL数据文件必须和共享内存运行在支持所需语义的本地文件系统；不要放NFS、SMB或云盘挂载目录。备份不能只复制正在写的`.sqlite3`而忽略日志。无论模式都使用下面的SQLite在线备份API。

## 备份

以能读取专用环境文件的应用账户执行；不要把密钥写在命令行参数里：

```bash
APP_ENV_FILE=/etc/campus-start/prod.env \
  /data/lx/campus-start/prod/current/.venv/bin/python \
  /data/lx/campus-start/prod/current/scripts/ops.py \
  backup --output /data/lx/campus-start/prod/backups
```

路径必须替换为实际部署值。脚本调用SQLite backup API，做quick_check，生成唯一时间名的备份、SHA256摘要、schema_version、HMAC密钥指纹以及最新删除清单。字段仍是加密状态，但备份含可关联元数据，仍是私有资料。权限0600，目录0700。

默认只自动清理命名为`campus-backup-*`且超过30天的滚动备份；不会擅自删除其他文件。恢复前另存的`before-restore-*`文件需管理员按同样期限独立清理。

定时器每天约03:20执行，顺序为：一致性备份→到期清理→重新导出最新删除清单。执行时间以server时区为准，不假定北京时间。启用后观察日志和实际产物，不能只确认timer“enabled”就算备份成功。

## 到期清理与名册

```bash
# 默认只预览，不删除
APP_ENV_FILE=/etc/campus-start/prod.env python scripts/ops.py retention
# 明确批准后执行
APP_ENV_FILE=/etc/campus-start/prod.env python scripts/ops.py retention --apply
```

提交记录按submitted_at，草稿按created_at计算期限，不允许频繁访问无限延长保存。删除与墓碑写入在同一数据库事务中。过期管理员会话、限流项及超期审计也会清理。

授权名册CSV列名必须是 `student_id,name`，学号列必须保留字符串前导零：

```bash
APP_ENV_FILE=/etc/campus-start/prod.env python scripts/ops.py import-roster --file /private/approved-roster.csv
APP_ENV_FILE=/etc/campus-start/prod.env python scripts/ops.py import-roster --file /private/approved-roster.csv --apply
```

先预览错误与行数再apply；输出不打印名册正文。启用ROSTER_REQUIRED前先导入并用虚构专用测试项核验。活动结束另行执行 `clear-roster`，仍需 `--apply`才真的删除。明文导入文件需负责人按授权目的及时清理，不保存到本包目录。

## 异地备份

本包没有默认上传到第三方，也没有擅自使用杭州VPS储存学生库。agent应依据用户批准的备份主机、地域、权限与目的，将加密字段的DB备份、摘要和**持续更新的删除清单**传到独立受控位置。数据密钥必须通过单独秘密管理渠道备份，不能和数据库一起公开。

同一硬盘的backup子目录只能防部分误操作，不是主机损坏保障。异地同步至少采用认证加密传输，限制读写账号；设定保留期限和失败告警。RPO/RTO需实测，不在本包预设保证值。

## 恢复前置条件

先停止应用和备份timer；确认不存在其他写入者。选择校验通过的备份，使用**当前最新删除清单**而不是随旧备份附带的旧清单，避免撤回的人重新出现。

```bash
sudo systemctl stop campus-start-prod-backup.timer
sudo systemctl stop campus-start-prod.service
# 在原库尚可读时先导出最新墓碑，文件放私有目录
APP_ENV_FILE=/etc/campus-start/prod.env python scripts/ops.py export-deletions --output /private/deletions-current.json

APP_ENV_FILE=/etc/campus-start/prod.env python scripts/ops.py restore \
  --backup /private/campus-backup-CHOSEN.sqlite3 \
  --ledger /private/deletions-current.json \
  --replace --service-stopped
```

`--service-stopped`是操作者对真实停机的确认，脚本不会替你停止远端进程。没有这个标志拒绝执行；已有目标必须明确`--replace`。必须保留原加密密钥和HMAC密钥；脚本核验摘要、密钥指纹、可解密样本、quick_check，重放删除UUID并清空管理员会话。

恢复过程输出临时DELETE模式数据库。生产本来就是默认DELETE时直接启动；之前明确使用WAL的环境，须在所有写入者停止、已修复版本核验后做单独授权的离线journal_mode转换，否则应用会因模式不一致而拒绝启动。不要绕过这个保护。

如果原库损坏又没有最新删除清单，不能拿一个旧清单就宣称撤回记录不会复活；需负责人从私有审计/导出记录重建删除范围或暂停恢复开放。恢复后比对记录数、抽样结果、已删除样本、回执与后台登录，再恢复服务和timer。

## 升级和口令

版本更新使用独立release+venv，保留current旧目标和环境文件。同schema回滚只切代码，不还原DB；恢复旧DB会丢失后续提交，需要明确数据恢复决定。

修改管理员口令用 `scripts/hash_password.py` 交互生成新哈希，写入私有环境文件，并在停机维护中清理旧会话后重启。`DATA_ENCRYPTION_KEY`及`INDEX_HMAC_KEY`不能按口令轮换方式随便替换。EDGE_TOKEN变化须两端同步更新、检查并安排短暂维护。

## 应急检查清单

进程与监听 → 本地存储容量/权限 → 本项目日志 → 杭州到server连通 → 入口token一致 → Nginx语法/上游状态 → TLS与域名 → 学生端重试和回执。只在本站范围修复，避免伤及研究数据和远程运维入口。