from prepare import HERE, idle, sha, save
import shutil

idle('before_project_format_retry')
archive = HERE / 'attempt_01_project_syntax_failure'
archive.mkdir()
for name in ['project.pds', 'controller.log', 'compile_shell.log', 'flow_result.json']:
    shutil.copyfile(HERE / name, archive / name)
data = (HERE / 'project.pds').read_bytes()
for name in ['v7_sdt_bus.v', 'v7_sfd_candidate.v']:
    old = ('(_file "rtl/' + name + '" (_format verilog))').encode()
    new = ('(_file "rtl/' + name + '"\n                    (_format verilog)\n                )').encode()
    assert data.count(old) == 1
    data = data.replace(old, new)
(HERE / 'project.pds').write_bytes(data)
save('project_format_retry.json', {'failure':'Flow-0130', 'failed_project_sha256':sha(archive / 'project.pds'),
                                 'corrected_project_sha256':sha(HERE / 'project.pds'), 'rtl_or_constraints_changed':False})
for name in ['controller.log', 'compile_shell.log', 'flow_result.json']:
    (HERE / name).unlink()
