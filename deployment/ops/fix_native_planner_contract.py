"""Align the installed Paper2Code request with its existing YAML validator."""
from pathlib import Path

root=Path('C:/Users/DEVELOPER/Documents/ChatGPT/小研究/DeepCode_MCP')
for path in [root/'repo/DeepCode/workflows/agent_orchestration_engine.py',root/'DeepCode-env/Lib/site-packages/workflows/agent_orchestration_engine.py']:
    text=path.read_text(encoding='utf8')
    old='Based on this paper, generate a complete implementation plan detailed enough for independent implementation.'
    new=old+' Return only the final YAML plan, with these exact required keys: file_structure, implementation_components, validation_approach, environment_setup, implementation_strategy. This is a parser contract, not optional prose formatting. Do not write the plan as Markdown headings.'
    if new not in text:
        assert old in text;text=text.replace(old,new,1)
    old_retry='''            new_max_tokens, new_temperature = _adjust_params_for_retry(
                enhanced_params, retry_count
            )'''
    new_retry='''            message += "\\nThe previous answer failed the plan parser. Missing keys: " + ", ".join(missing) + ". Return a corrected YAML object containing all five required keys, without prose headings."
            new_max_tokens, new_temperature = _adjust_params_for_retry(
                enhanced_params, retry_count
            )'''
    if new_retry not in text:
        assert old_retry in text;text=text.replace(old_retry,new_retry,1)
    old_gate='if completeness_score >= 0.8 and plan_validation.get("valid", False):'
    new_gate='if plan_validation.get("yaml_valid", False) and plan_validation.get("valid", False):'
    # A valid concise YAML plan was being rejected for omitting Markdown fences
    # and for being shorter than an unrelated 8,000-character heuristic.
    if new_gate not in text:
        assert old_gate in text;text=text.replace(old_gate,new_gate,1)
    compile(text,str(path),'exec');path.write_text(text,encoding='utf8')
    print('Updated native planner contract and actual validation feedback:',path)
