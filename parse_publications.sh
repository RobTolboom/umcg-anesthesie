# #!/usr/bin/env bash

set -e

#curl -o content/diag.bib \
#     -s -f -S \
#     -L https://raw.githubusercontent.com/DIAGNijmegen/Literature/main/diag.bib

#curl -o content/cara.bib \
#     -s -f -S \
#     -L https://raw.githubusercontent.com/DIAGNijmegen/Literature/main/cara.bib

#curl -o content/fullstrings.bib \
#     -s -f -S \
#     -L https://raw.githubusercontent.com/DIAGNijmegen/Literature/main/fullstrings.bib

python3 ./bibliography/bibparser.py umcg-anes
#python3 ./bibliography/bibparser.py cara
