"""Read-only ELF64 comparison for rebuilt Sail; no binary rewriting/admission.

The three Dune installation slots are checked as exact 4096-byte payloads.
This explains allocated-section differences, NOT translator correctness or
equivalence of the complete toolchain/host environment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from source_snapshot import require


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sections(data):
    require(len(data) >= 64 and data[:6] == b'\x7fELF\x02\x01','expected ELF64 little endian')
    offset = struct.unpack_from('<Q',data,40)[0]
    size,count,names_index = struct.unpack_from('<HHH',data,58)
    require(size == 64 and count > 0 and 0 < names_index < count and offset+size*count <= len(data),
            'unsupported or truncated ELF section table')
    rows = [struct.unpack_from('<IIQQQQIIQQ',data,offset+i*size) for i in range(count)]
    names = rows[names_index]
    require(names[1] == 3 and names[4]+names[5] <= len(data),'invalid ELF string table')
    table = data[names[4]:names[4]+names[5]]
    result = {}
    for idx,kind,flags,address,start,length,link,info,align,entry in rows:
        require(idx < len(table),'ELF name outside string table')
        end = table.find(b'\0',idx)
        require(end >= idx,'unterminated ELF name')
        name = table[idx:end].decode('ascii')
        if not name: continue
        require(name not in result,'duplicate ELF section')
        require(kind == 8 or start+length <= len(data),'truncated ELF section')
        result[name] = {'type':kind,'flags':flags,'address':address,'size':length,'align':align,
                        'data':None if kind == 8 else data[start:start+length]}
    return result


def slot(payload):
    require(isinstance(payload,bytes),'slot payload must be bytes')
    value = b'='+str(len(payload)).encode()+b':'+payload
    require(len(value) <= 4096,'Dune slot too long')
    return value.ljust(4096,b' ')


def installation_slots(prefix, opam_prefix):
    prefix,opam_prefix = Path(prefix),Path(opam_prefix)
    require(prefix.is_absolute() and opam_prefix.is_absolute(),'prefixes must be absolute')
    ocaml = str(opam_prefix/'lib/ocaml').encode()
    return {'sail_plugins':str(prefix/'share/libsail').encode(), 'ocaml_stdlib':ocaml,
            'ocaml_search_path':b'hardcoded\0'+ocaml+b'\0'+str(opam_prefix/'lib').encode()}


def data_slot_audit(left,right,old_slots,new_slots):
    require(len(left) == len(right),'data section size differs')
    require(set(old_slots) == set(new_slots) == {'sail_plugins','ocaml_stdlib','ocaml_search_path'},
            'unexpected installation slot list')
    expected = left
    evidence = {}
    ranges = []
    for name,old_value in old_slots.items():
        old,new = slot(old_value),slot(new_slots[name])
        require(left.count(old) == 1 and right.count(new) == 1,'installation slot missing or repeated: '+name)
        offset = left.index(old)
        require(right.index(new) == offset,'installation slot moved: '+name)
        require(all(offset+4096 <= start or offset >= end for start,end in ranges),'overlapping slots')
        ranges.append((offset,offset+4096))
        expected = expected[:offset]+new+expected[offset+4096:]
        evidence[name] = {'offset':offset,'size':4096,'old_payload':old_value.decode(),
                          'new_payload':new_slots[name].decode(),'old_sha256':digest(old),'new_sha256':digest(new)}
    require(expected == right,'data differs outside the three exact installation slots')
    return evidence


def compare(left_path,right_path,slot_prefixes=None):
    left_data,right_data = Path(left_path).read_bytes(),Path(right_path).read_bytes()
    left,right = sections(left_data),sections(right_data)
    require(left.keys() == right.keys(),'ELF section name sets differ')
    changed = []
    allocated_changed = []
    for name in left:
        a,b = left[name],right[name]
        if a != b:
            changed.append(name)
            if (a['flags'] | b['flags']) & 2: allocated_changed.append(name)
        if (a['flags'] | b['flags']) & 2:
            require({k:v for k,v in a.items() if k != 'data'} ==
                    {k:v for k,v in b.items() if k != 'data'},'allocated section layout differs: '+name)
    require(left['.text'] == right['.text'],'machine code differs')
    result = {'baseline_sha256':digest(left_data),'candidate_sha256':digest(right_data),
              'text_sha256':digest(left['.text']['data']), 'text_size':left['.text']['size'],
              'changed_sections':sorted(changed),'changed_allocated_sections':sorted(allocated_changed),
              'allocated_layout_identical':True,'whole_file_identical':left_data == right_data,
              'binary_rewritten':False,'tool_approved':False,'semantic_equivalence_claimed':False}
    if slot_prefixes:
        require(set(allocated_changed) <= {'.data','.note.gnu.build-id'},'unexplained allocated section change')
        old_prefix,old_opam,new_prefix,new_opam = slot_prefixes
        result['data_slots'] = data_slot_audit(left['.data']['data'],right['.data']['data'],
                    installation_slots(old_prefix,old_opam),installation_slots(new_prefix,new_opam))
        result['other_data_bytes_identical'] = True
    else:
        require(set(allocated_changed) <= {'.note.gnu.build-id'},'plugin non-build-ID allocated sections differ')
        result['allocated_bytes_except_build_id_identical'] = True
    return result


def audit_installation(report_path):
    root = Path(__file__).resolve().parents[1]
    evidence = Path(report_path).read_bytes()
    require(digest(evidence) == 'a765bc5f4cbaa9af62909ea9cd1e1d2af50a5b9f8437aaf80a7be0cf91b88739',
            'install report is not the reviewed candidate')
    previous = json.loads(evidence)
    old,new = Path(previous['baseline_prefix']),Path(previous['prefix'])
    old_opam = Path('/home/clair/.opam/5.4.1')
    new_opam = Path(previous['opam_root'])/previous['switch']
    old_plugins = sorted(p.name for p in (old/'share/libsail/plugins').glob('*.cmxs'))
    new_plugins = sorted(p.name for p in (new/'share/libsail/plugins').glob('*.cmxs'))
    require(len(old_plugins) == 10 and old_plugins == new_plugins,'native plugin inventory drift')
    paths = ['bin/sail', *['share/libsail/plugins/'+p for p in old_plugins]]
    rows = {}
    for name in paths:
        for prefix,key in [(old,'baseline_closure_before'),(new,'installed_closure')]:
            require(digest((prefix/name).read_bytes()) == previous[key]['files'][name]['sha256'],
                    'installation binary changed: '+name)
        rows[name] = compare(old/name,new/name,(old,old_opam,new,new_opam) if name == 'bin/sail' else None)
    return {'schema_version':1,'status':'allocated_sections_accounted_not_tool_admission',
            'install_report':str(Path(report_path).resolve()),'install_report_sha256':digest(evidence),
            'audit_source_sha256':digest(Path(__file__).read_bytes()),
            'require_source_sha256':digest((root/'scripts/source_snapshot.py').read_bytes()),
            'baseline_prefix':str(old),'candidate_prefix':str(new),'native_plugins_audited':10,
            'binary_audits':rows,'binary_rewritten':False,'tool_approved':False,
            'elf_headers_debug_and_all_file_padding_equivalence_claimed':False,
            'host_dynamic_libraries_audited':False,'semantic_equivalence_claimed':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(),'audit output already exists')
    result = audit_installation(args.install_report)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2); stream.write('\n')
    print(json.dumps({'status':result['status'],'output':str(args.output),
                      'sha256':digest(args.output.read_bytes())}))


if __name__ == '__main__':
    main()
