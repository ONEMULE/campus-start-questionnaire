# 08 / 开发交接、接口与素材

## 技术栈和目录

前端纯HTML/CSS/JS，不需要Node构建；Node只用于可选语法检查。后端FastAPI/Pydantic，SQLite由Python标准库连接，qrcode生成二维码，cryptography提供字段认证加密。requirements.txt锁定直接依赖；requirements.lock.txt记录实际测试环境的运行时依赖闭包，不宣称覆盖所有平台。

```text
backend/        接口、状态、加密、路由与计分
content/        版本化52节点题库
web/            手机页面、管理后台、隐私、二维码
config/         非秘密模板
scripts/        初始化、候选配置、健康检查、数据运维
 deploy/templates/  两端部署模板
 tests/         单元/API测试及真实浏览器复测脚本
 docs/          需求、运行规范、API模式、可读题库
 reports/       本次测试、覆盖审计、截图（全部虚构记录）
 reference/     旧Word和旧源码，只读追溯
```

## 页面入口

`/`学生入口；`/admin`后台；`/privacy`说明；`/qr`二维码页；`/qr.png`固定配置URL的PNG。所有路径在同一个源，不提供跨域开放API。不需要学生安装Tailscale。微信只是作为网页容器，真实域名是否可访问仍需真机验收，不保证平台自动免审或始终无拦截。

## API契约

请求和响应详见 `docs/openapi.json`（由当前代码生成，线上不暴露交互式API文档）。关键端点：

| 方法 | 路径 | 权限 / 用途 |
|---|---|---|
| GET | `/api/config`、`/api/content` | 公开元信息和题目，不含秘密 |
| POST | `/api/sessions` | 姓名/学号/同意版本，可选参与口令；首次登记201 |
| GET | `/api/sessions/me` | Bearer恢复码；本人记录 |
| PUT | `/api/sessions/me/progress` | Bearer；answers+递增revision |
| POST | `/api/sessions/me/submit` | Bearer；完整answers；服务端验证和幂等回执 |
| DELETE | `/api/sessions/me` | Bearer；撤回删除 |
| POST | `/api/preview` | 仅开发/独立staging的无身份试玩，不保存记录 |
| POST | `/api/admin/login` | 管理员账号口令；返回CSRF并设置会话cookie |
| GET | `/api/admin/me` | 会话状态与CSRF |
| POST | `/api/admin/logout` | 会话+CSRF |
| GET | `/api/admin/participants` | 会话；分页、学号、状态 |
| GET | `/api/admin/participants/{id}` | 会话；记录详情 |
| POST | `/api/admin/participants/{id}/review` | 会话+CSRF；role、四项scores、note |
| POST | `/api/admin/participants/{id}/rotate-access` | 会话+CSRF；核验后的恢复码补发 |
| DELETE | `/api/admin/participants/{id}` | 会话+CSRF；删除 |
| GET | `/api/admin/export.csv`、`/api/admin/audit` | 会话；受控导出与审计 |

401为凭证无效；403为来源/授权/CSRF失败；409为重复或状态冲突；422为答案或字段不合规；429为限流；413为过大请求。错误返回不应回显姓名学号或口令。服务端所有参与者读取都依据高熵恢复token，不提供公开的按学号查询接口。

## 本地调试

在独立开发目录创建venv，执行 `bootstrap_local.py`。脚本只用于development，生成的口令和密钥不要复制到生产。没有.env时应用因缺少关键参数拒绝启动，这是预期行为，不是让agent硬编码默认口令。

```bash
python -m pip install -r requirements-dev.txt
pytest -q
node --check web/app.js
node --check web/admin.js
node --check web/info.js
```

真实浏览器复测脚本 `tests/ui_smoke.py` 会写入虚构测试记录，必须指向启用demo的独立staging数据库，并以环境变量私下提供UI_TEST_ADMIN_PASSWORD。它不会自动清理整个数据库。若运行环境禁止浏览器导航，报告限制，不修改系统安全策略来绕过；本次采用离线DOM注入+本地API桥检查交互，原生HTTP浏览器/微信验收留给部署环境。

## 修改题目

编辑 `content/questions.v1.json`；保持ID稳定和effects字段合法，保留single/multi/allocation/worksample/contact/mbti契约。新增分支必须同时修改后端sequence、前端sequence、答案校验和5路线测试。新增题不能直接让已开始的旧会话读到不兼容结构；应新建content_version并明确旧会话如何结束。

人工校对全文可用 `docs/QUESTION_BANK.md`，它由JSON生成。以JSON为单一数据源，不让Word、JS常量、后端常量各自保存不同题目。`scripts/audit_content.py`生成路径与指标覆盖报告。

## 修改界面和文案

品牌、页面标题与页脚分布在web各HTML、app.js、admin.js、info.js、backend/main.py和maintenance.html；改名时全文检索，但不要修改reference里的历史原件。颜色在styles.css变量中。字体使用用户设备系统字体，不分发字体文件。

无外部CDN，适合在自有域名统一提供资源；不要引入会发送学生行为的第三方分析脚本。UI修改要检查320/390/768宽度、长学号、中文换行、极长作品、键盘聚焦、返回重算、离线提示和后台表格横向滚动。

## 照片资产

将经过授权、已去除GPS等EXIF敏感元数据的8张JPEG放到 `web/assets/photos/0.jpg` … `7.jpg`，再设置PHOTO_TASK_ENABLED=true。Settings会检查文件存在，否则拒绝启用。提供拍摄/使用授权台账、编号到图片说明的映射和公平评阅标准；不要使用陌生人的肖像素材或把示意卡伪装成真实摄影测评。

建议把图片压缩到合适移动端尺寸和体积，单图避免过大；不得把学生姓名或学号放在照片文件名。当前不是上传功能，不需要学生向后端上传任意文件。

## 离线依赖准备

本包不是携带所有二进制wheel的离线镜像。若server无公网，agent须在**相同Python版本、CPU架构、Linux兼容平台**的受控联网环境创建wheelhouse，再通过授权通道传输：

```bash
python -m pip download -r requirements.lock.txt -d wheelhouse
# 目标环境验证平台匹配后：
python -m pip install --no-index --find-links wheelhouse -r requirements.lock.txt
```

只下载对应平台可用轮子；缺轮子时先在匹配环境构建并测试，不用不明二进制替代。为wheelhouse另建哈希清单；本包MANIFEST不替新下载依赖背书。

## 后续迭代优先级

第一优先：目标环境与真机验收、名册授权/学号格式、真实照片、数据管理责任。第二优先：题目理解度、角色关系和更多玩法、低覆盖维度修正。第三优先：多管理员权限/SSO、异地备份自动化、外部监控和更大规模数据库。心理测量验证是另一个研究工作流，不能把软件测试结果充当它的完成证据。