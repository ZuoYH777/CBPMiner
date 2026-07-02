# CBPMiner
CBP Miner is developed using Python, which takes as input a CSV-based event log, and then automatically discovers a collaborative business process (CBP) specified in a dot file. If the discovered CBP is rational, then it is returned directly; otherwise, a set of coordinators are generated, each of which is also described in a dot file. These coordinators can be synthesized to control the discovered CBP to become rational again.
# Guideline for using CBPMiner
1. One needs to first run the file "Ours_viewer_1.py";
2. One then imports a CSV-based event log such as PO_Log.csv (available at: https://doi.org/10.6084/m9.figshare.29568722.v1);
3. One finally clicks the "Generate" button, and a CBP described in a dot file is discovered. In particular, if the discovered CBP is rational, then it is returned directly; otherwise, a set of coordinators are generated, each of which is also described in a dot file.
   
![18991751294084_ pic](https://github.com/user-attachments/assets/a7817168-e460-4992-a2c6-805f4fbd35bf)
