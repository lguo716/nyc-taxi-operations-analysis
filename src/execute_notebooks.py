import os
import sys
import json
from pathlib import Path
import nbformat
from nbclient import NotebookClient

from .config import ROOT,ensure_dirs
from .utils import write_json,utc_now

def execute():
    ensure_dirs()
    kernels=ROOT/".jupyter/kernels/nyc-taxi"
    kernels.mkdir(parents=True,exist_ok=True)
    write_json(kernels/"kernel.json",{"argv":[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"],"display_name":"NYC Taxi Python 3.12","language":"python"})
    os.environ["JUPYTER_PATH"]=str(ROOT/".jupyter")
    os.environ["JUPYTER_RUNTIME_DIR"]=str(ROOT/"data/tmp/jupyter")
    records=[]
    for path in sorted((ROOT/"notebooks").glob("*.ipynb")):
        nb=nbformat.read(path,as_version=4)
        NotebookClient(nb,timeout=180,kernel_name="nyc-taxi",resources={"metadata":{"path":str(ROOT)}}).execute()
        nbformat.write(nb,path)
        records.append({"notebook":path.name,"code_cells":sum(c.cell_type=="code" for c in nb.cells),"errors":sum(o.output_type=="error" for c in nb.cells if c.cell_type=="code" for o in c.outputs),"executed":all(c.execution_count is not None for c in nb.cells if c.cell_type=="code")})
        print(path.name,"executed")
    write_json(ROOT/"reports/notebook_verification.json",{"verified_at":utc_now(),"notebooks":records,"passed":all(x["executed"] and x["errors"]==0 for x in records)})

if __name__=="__main__":execute()
