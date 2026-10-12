"""Offline read-only reference extraction. Does not launch tools or modify map02."""
from pathlib import Path
import hashlib,html,json,re
H=Path(__file__).resolve().parent
R=H.parent/'physical_pack_control_reference01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    evidence=H/'evidence';evidence.mkdir(exist_ok=True)
    extracts=[]
    for name,patterns in [
        ('help_0.html',[r'5\.14\s+syn_noprune',r'注意：\s*syn_noprune']),
        ('help_2.html',[r'9\.9\s+dev_map',r'def_inst_site inst_name site_name',r'生成的约束文件中均带有 no_check']),
        ('help_4.html',[r'注意加 pcf 和 rcf 文件的顺序和位置']),
        ('help_5.html',[r'2\.3\.4\.6\s+PAP_LOC',r'2\.3\.4\.7\s+PAP_REGION'])]:
        p=R/name
        text=html.unescape(re.sub('<[^>]+>',' ',p.read_bytes().decode('utf-8')))
        text=re.sub(r'\s+',' ',text)
        for pattern in patterns:
            hits=list(re.finditer(pattern,text))
            assert hits,(name,pattern)
            m=hits[-1]
            extracts.append({'source':str(p),'sha256':sha(p),'pattern':pattern,'text_offset':m.start(),'exact_excerpt':text[max(0,m.start()-100):m.start()+2600]})
    samples=R/'actual_routed_register_sites.json'
    actual=json.loads(samples.read_bytes())
    chosen=[r for r in actual['actual_placed_register_samples'] if r['place_fields'] in [['impl_devCQ0','CLMA','33','450'],['impl_devCQ0','CLMA','45','462']]]
    assert len(chosen)==2
    result={'status':'OFFLINE_PREPARED_NOT_EXECUTED','requires':'Completed actual map02 final_result FAIL and independent audit; serial queue clear',
            'references':extracts,'actual_sites_reference':{'file':str(samples),'sha256':sha(samples),'receipt':actual},
            'proposed_variable':'Two distinct physical sites for two connected explicit GTP_DFF_CE stages; same RTL, INIT=0, async clear, CE=1, positive clock and cycle semantics in both arms',
            'proposed_sites':['CLMA_33_450','CLMA_45_462'],'proposed_impl':'impl_devCQ0',
            'not_yet_proven':['raw PLACE implementation token validity as def_inst_site impl argument','pre-map logical GTP register target recognition','pre-map constraint propagation through FF packing','packing inhibition by distinct physical sites'],
            'documented_limitations':['PDS guide documents placement constraints, not anti-packing effect','PDS route-constraint example loads PCF after Device Map; it does not establish pre-map logical GTP target recognition','PAP_LOC documentation typically concerns special-placeable resources; no blanket GTP FF guarantee','no_check and silent missing-target acceptance prohibited'],
            'acceptance':['Actual logs free of ERROR/FATAL/unknown/ignored/Tcl failure','Constraint target existence before and after map, actual CDB/PCF plus export_fdc roundtrip matching both targets/sites','Two distinct actual mapped cells with D, CLK, reset, Q, original Q-to-D adjacency and INIT/reset/CE/clock contract','If impl token rejected, preserve failure; never silently substitute FGA or reinterpret raw PLACE','TwoFF probe success does not satisfy production 60-cell gate; require subsequent full isolated experiment'],
            'PDS_started':False,'production_changes':False,'selected_actual_samples':chosen}
    (evidence/'official_site_probe_basis.json').write_text(json.dumps(result,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
    print('Offline official site probe basis prepared; no PDS or production writes')
if __name__=='__main__':main()
