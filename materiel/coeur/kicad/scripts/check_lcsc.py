import sys
from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
api = EasyedaApi()
for cid in sys.argv[1:]:
    try:
        d = api.get_cad_data_of_component(lcsc_id=cid)
        if not d: print(cid, "-> INTROUVABLE"); continue
        t = d.get("title"); desc = d.get("description","")
        pkg = d.get("packageDetail",{}).get("title") or d.get("dataStr",{}).get("head",{}).get("c_para",{}).get("package")
        para = d.get("dataStr",{}).get("head",{}).get("c_para",{})
        print(cid, "->", t, "|", pkg, "|", para.get("Manufacturer"), "|", (desc or "")[:90])
    except Exception as e:
        print(cid, "-> ERR", e)
