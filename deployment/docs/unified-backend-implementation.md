# 统一会话服务端实施回执

2026-11-02。按《DeepPartner统一产品框架》完成本机源代码实现；没有修改Tutor核心、配置或线上服务，没有调用模型或重跑生产工作流。

## 当前行为

`POST /research/api/projects/{pid}/annotations/submit` 支持可选 `session_id`、`operation_id`。提交前用当前登录身份请求项目原生工作区中的session，拒绝其他用户/工作区；有效会话通过原生 `/ws v2 start_turn` 继续。operation_id映射为稳定client_submission_id，返回实际 `session_id/turn_id/url/operation_id`，批注locator保存native_session_id/native_turn_id/operation_id。省略session的旧客户端仍由原生运行时创建会话。没有新增聊天存储。

`GET /research/api/projects/{pid}/native-session?session_id=&turn_id=` 提供受认证的项目会话/turn校验，供Dify桥复用。`agent-receipt` 对可选会话/turn先校验，再把session_id/turn_id/operation_id持久化到原有agent.receipt事件；旧回执缺少这些字段仍可保存。

`POST /research/api/projects/{pid}/figure/chat` 的可选 `embedded:true`、session_id、operation_id也已接入同一原生会话。保留selection/changes/revision/edit_session及PNG快照，先用既有Matplotlib preview核验当前草稿，再保存批注及figure.feedback.submitted事件；返回顶层真实session_id/turn_id/url/operation_id/question_id。嵌入模式不写.workbench/figure-chats副本，也不另排summary模型；include_context=false时不向原生会话发送图片、对象或草稿。旧独立图形窗口逻辑保留。

WS handoff将有效HTTP bearer转换成原生dt_token Cookie头，不把凭据放URL或返回内容。提交接收逻辑等待真实session和turn都有值，避免过早把只有session的帧当完整接收结果。

bridge Delivery增加可选turn_id；prepare、commit都在写入前调用工作台native-session校验。回执带原生身份，verify_delivery在已有精确历史检查中同时匹配保存下来的可选session/turn/operation。已保存的旧payload没有turn_id仍能幂等查询；没有链接的旧回执不会因缺少新字段失败。

## 桌面发现接口

受认证 `GET /research/api/desktop/manifest?frontend_version=0.4.0&protocol_version=2.0` 返回：

```json
{
  "schema_version":"desktop-manifest.v1",
  "product":"DeepPartner",
  "protocol":{"minimum":"2.0","maximum":"2.0","current":"2.0"},
  "frontend":{"minimum":"0.4.0","current":"0.4.0","update_policy":"manual"},
  "compatibility":{"compatible":true,"frontend_supported":true,"protocol_supported":true,"upgrade_required":false,"reasons":[]},
  "standards":{"version":"当前server.standards.VERSION","endpoint":"/research/api/standards"},
  "capabilities":{"status":"available","endpoint":"/api/capabilities/registered","items":[]},
  "workflows":[],
  "updates":{"server":"new_tasks","frontend":"manual","remote_code_execution":false}
}
```

示例items/workflows只表示字段位置；真实响应直接取原生注册能力，并声明已有Dify交付、网页证据、事件处理和协调应用的真实app_id。没有本轮运行时检查则availability=unknown；没有发布版本证据则publication.status=unknown、version=null，不拿DSL schema_version或应用ID假装已发布版本。可选受控文件 `WORKBENCH_DESKTOP_WORKFLOWS_FILE`（默认WORKBENCH_DATA/desktop-workflows.json）仅承载部署方观察到的app_id、published_version、source、observed_at，不能承载客户端代码。证据中的额外字段不会返回。

接口有内容ETag、private/must-revalidate和Cookie/Authorization Vary；匹配If-None-Match返回304，仍先认证。capability目录不可用时保留manifest并明确unavailable，不泄露上游异常。0.4.0以下前端或不支持的协议显示升级原因。字体目录存在时静态挂载 `/research/fonts`；未知API仍404。

## 修改文件与验证

- 正式后端：`D:/Development/research-workbench/server/reviews.py`、`server/app.py`、新增`server/desktop_manifest.py`。
- 后端测试：新增`tests/test_desktop_unification.py`、`tests/test_desktop_manifest.py`。
- Dify桥：`D:/Development/询问/dify-research-deployment/bridge/delivery.py`、`tests/test_delivery.py`测试后端边界适配、新增`tests/test_delivery_identity.py`。

新会话关联/manifest测试最终13 passed；此前同一实现连同quality API/receipt已有回归34 passed（之后新增一项native-session权限测试）。桥delivery/identity/automation/workflow identity测试42 passed。四个变动服务端Python模块py_compile通过。完整bridge tests尝试一次因本地选用DeepTutor Python环境缺fastmcp而在收集阶段停止；随后明确限定相关测试通过，没有安装或替换依赖。

补充图形嵌入后desktop测试为16 passed，包含真实Matplotlib注册、编辑会话、preview、版本拒绝和截图/草稿传递。测试所用DeepTutor环境没有Matplotlib，按项目requirements精确版本在系统TEMP隔离target安装matplotlib3.11.2/cloudpickle3.1.2供测试，不修改该venv依赖。Windows长路径测试夹具改用简短临时根目录。

测试使用真实工作台ASGI路由、SQLite项目/批注/历史和现有质量逻辑；原生HTTP/WS与Dify边界用可控替身，未消耗模型额度。线上bearer认证、原生真实turn接收和统一UI回流仍需协调部署后有限验证。服务文件由主协调者统一部署，本子任务没有重启服务。
