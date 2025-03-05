# Relay Server

## Installation

1. Make sure you have conda properly setup on your system (https://docs.anaconda.com/miniconda/install/)
2. Run `bash create_env.sh` from within this directory. This creates a new conda environment called `relay_server` which contains all the necessary dependencies.

## Usage

1. Activate the conda environment with `conda activate relay_server`.
2. Copy relevant documentation into the `data/pdf_rag_files` directory and convert them to markdown using the `pdf2md.py` script. Beacuse of copyright issues, we cannot include those files in this repository, but a quick google search will bring up enough resources.
2. Start the relay server with `python3 main.py`.

# Additional Features

- If you want to add additional reference documents for the RAG, please put them into `./data/pdf_rag_files` and run `python3 pdf2md.py` which converts all the files to markdown and saves them `/data/md_rag_files`. Additional pip packages (e.g., `pymupdf4llm`) might be necessary to install
- If you want to update all the METARs to the current weather conditions, you can do so using `python3 download_current_metar.py`.
- If you only want to experiment with the LLM and prompt engineering, but don't have X-Plane or the Toliss A320NEO available, you can run `python3 mock_xp_plugin.py` which simulates a call from the simulator to the relay server.