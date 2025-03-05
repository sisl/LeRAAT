# This script converts all the pdf files that are located in the pdf_rag_files directory into markdown and saves the resulting markdown in md_rag_files directory

import pymupdf4llm
import pathlib
from glob import glob
import os

os.makedirs("./data/md_rag_files",exist_ok=True)

for fn in glob("./data/pdf_rag_files/*.pdf"):

    md_text = pymupdf4llm.to_markdown(fn)
    
    file_stem = pathlib.Path(fn).stem
    
    pathlib.Path(f"./data/md_rag_files/{file_stem}.md").write_bytes(md_text.encode())    