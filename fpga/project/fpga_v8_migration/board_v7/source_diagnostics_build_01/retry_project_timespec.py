from prepare import HERE, idle, sha, save
import shutil

idle('before_project_timespec_retry')
archive = HERE / 'attempt_02_project_timespec_failure'
archive.mkdir()
for name in ['project.pds', 'controller.log', 'compile_shell.log', 'flow_result.json']:
    shutil.copyfile(HERE / name, archive / name)
data = (HERE / 'project.pds').read_bytes()
for name in ['v7_sdt_bus.v', 'v7_sfd_candidate.v']:
    old = ('(_file "rtl/' + name + '"\n                    (_format verilog)\n                )').encode()
    new = old.replace(b'(_format verilog)', b'(_format verilog)\n                    (_timespec "2026-10-06T10:32:26")')
    assert data.count(old) == 1
    data = data.replace(old, new)
(HERE / 'project.pds').write_bytes(data)
save('project_timespec_retry.json', {'failure':'Flow-0130', 'failed_project_sha256':sha(archive / 'project.pds'),
                                   'corrected_project_sha256':sha(HERE / 'project.pds'), 'rtl_or_constraints_changed':False})
for name in ['controller.log', 'compile_shell.log', 'flow_result.json']:
    (HERE / name).unlink()
