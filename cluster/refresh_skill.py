from pathlib import Path
root=Path("/srv/deeptutor/data")
old="该连接的专用 SSH 身份仅能进入计算控制入口，不能被当作普通 SSH shell。"
new="该连接的凭据由计算服务持有，模型使用实验接口；集群接入网关的 SSH 限制并非安全沙箱，执行的是受信科研代码。"
for p in root.glob("**/research-compute-validation/SKILL.md"):
 s=p.read_text(); p.write_text(s.replace(old,new));print(p)
