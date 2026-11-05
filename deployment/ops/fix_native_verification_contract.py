"""Keep verification in the installed environment and discover nested generated projects."""
from pathlib import Path

base=Path('C:/Users/DEVELOPER/Documents/ChatGPT/小研究/DeepCode_MCP')
for folder in [base/'repo/DeepCode',base/'DeepCode-env/Lib/site-packages']:
    path=folder/'core/verification.py';text=path.read_text(encoding='utf8');old='map_python_to_current_interpreter=False,';new='map_python_to_current_interpreter=True,'
    assert old in text or new in text
    if old in text:text=text.replace(old,new,1)
    old_stdin='''        cwd=root,
        stdout=subprocess.PIPE,'''
    new_stdin='''        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,'''
    if new_stdin not in text:
        assert old_stdin in text;text=text.replace(old_stdin,new_stdin,1)
    path.write_text(text,encoding='utf8')
    path=folder/'workflows/code_implementation_workflow.py';text=path.read_text(encoding='utf8')
    old='''        commands = discover_verification_commands(code_directory)
        results: list[dict[str, Any]] = []
        for command in commands:'''
    new='''        roots = [code_directory]
        if not discover_verification_commands(code_directory):
            roots = [p for p in sorted(code_directory.iterdir())
                     if p.is_dir() and not p.is_symlink() and not p.name.startswith(".")
                     and discover_verification_commands(p)][:8]
        commands = [(root, command) for root in roots for command in discover_verification_commands(root)]
        results: list[dict[str, Any]] = []
        for verification_root, command in commands:'''
    if new not in text:
        assert old in text;text=text.replace(old,new,1)
        old_call='''                    run_verification,
                    code_directory,
                    command,'''
        assert old_call in text;text=text.replace(old_call,'''                    run_verification,
                    verification_root,
                    command,''',1)
        text=text.replace('''                        "command_id": command.id,
                        "command": list(command.argv),''','''                        "command_id": command.id,
                        "working_directory": str(verification_root),
                        "command": list(command.argv),''',1)
        compile(text,str(path),'exec');path.write_text(text,encoding='utf8')
    print('Updated native verification:',folder)
