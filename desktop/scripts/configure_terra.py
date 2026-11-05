"""Add a separate computer-control model to the existing DeepTutor provider."""
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0, "/app")
from deeptutor.services.config import get_model_catalog_service
from deeptutor.services.model_selection import list_llm_options

service = get_model_catalog_service()
catalog = service.load()
llm = catalog["services"]["llm"]
profile = next(p for p in llm["profiles"] if p["id"] == llm["active_profile_id"])
terra = next((m for m in profile["models"] if m.get("model") == "gpt-6.1-terra"), None)
added = False
if terra is None:
    source = next(m for m in profile["models"] if m["id"] == llm["active_model_id"])
    terra = copy.deepcopy(source)
    terra.update(id="desktop-terra", name="GPT-6.1 Terra · 电脑助手", model="gpt-6.1-terra", reasoning_effort="high")
    terra["capabilities"] = {**terra.get("capabilities", {}), "vision": True}
    profile["models"].append(terra)
    service.save(catalog)
    added = True
report = {"added": added, "computer_model": {"profile_id": profile["id"], "model_id": terra["id"], "model": terra["model"]}, "learning_default": list_llm_options(catalog)["active"]}
Path("/migration/desktop-terra-configuration.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False))
