# 10 / 官方资料与设计依据

核对日期：2026-09-05。以下链接供agent核验真实部署细节；不是为自创人格评分提供效度背书。软件版本以实际安装记录为准，部署前仍需复查安全更新。

1. FastAPI — Behind a Proxy：
   https://fastapi.tiangolo.com/advanced/behind-a-proxy/
   本包据此限定可信代理头来源，不把所有客户端声明的X-Forwarded-*当真。

2. Tailscale — Grants syntax / Access control：
   https://tailscale.com/docs/reference/syntax/grants
   https://tailscale.com/docs/features/access-control/grants
   参照当前官方语法审核源、目标与TCP端口授权；授权是叠加关系，必须检查现有策略的实际效果，不能只新增一条窄授权就宣称全局隔离完成。

3. SQLite — Write-Ahead Logging / WAL-reset bug：
   https://www.sqlite.org/wal.html
   https://www.sqlite.org/wal.html#walresetbug
   WAL依赖本地共享内存协调。2026年官方披露旧版WAL在特定多连接并发下存在损坏风险，修复版本包括3.51.3及指定回补分支。本包默认DELETE日志，WAL可选且有版本检查；不擅自更换科研系统运行时。

4. Nginx — Request limiting / Proxy module：
   https://nginx.org/en/docs/http/ngx_http_limit_req_module.html
   https://nginx.org/en/docs/http/ngx_http_proxy_module.html
   用于审核限流、proxy_bind、上游头处理与超时。需要依据实际Nginx版本做语法测试，不能直接用未知片段覆盖主配置。

5. 《中华人民共和国个人信息保护法》官方文本：
   https://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html
   备用官方转载：
   https://www.stats.gov.cn/gk/tjfg/xgfxfg/202503/t20250310_1958923.html
   本项目数据处理应明确目的、必要范围、告知同意与个人权利；重大权益影响的决定不应仅由自动化作出。实际采集主体、授权基础、保留期限与活动用途由负责人核对，本包不替代法律和学校流程审核。

6. Python sqlite3 — 连接与备份接口：
   https://docs.python.org/3/library/sqlite3.html
   运维使用SQLite备份API而不是简单复制正在写入的主库文件；依然需校验产物及进行恢复演练。

原始心理学文献线索保留在历史设计文档中，但该文档中的自创15维权重、分数带和招募线没有由这些文献直接验证。本版明确不宣传“科学成功筛选系统”。