# XPPlugin
## Installation

To install all the necessary requirements for the XPPlugin, follow these steps:

1. Install XPPython3 following the documentation (https://xppython3.readthedocs.io/en/latest/usage/installation_plugin.html).
2. Update the address and port where the relay server can be found in the `PI_AI_Assistant.py` file. The variable is called `SERVER_URI`.
2. Modify the path to the Python executable of XPPython3 in the `install_requirements.sh` file.
3. Open a terminal.
4. Navigate to the directory where the `install_requirements.sh` file is located:
    ```sh
    cd ~AirbusLLM/XPPlugin
    ```
5. Run the `install_requirements.sh` script:
    ```sh
    bash ./install_requirements.sh
    ```

This will install all the necessary dependencies for the XPPlugin and copy the `PI_AI_Assistant.py` file directly to the correct location.

## Usage

1. Open X-Plane and start a flight. 
2. Select *Reload Scripts* from the plugins menu. 

![XPPython3 Reload Scripts](./../figures/XPPython3_reload.png)

3. Select the *A320 LLM* which should open the GUI. Details about the usage and modes can be found in the technical report.
