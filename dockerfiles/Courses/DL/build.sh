# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


# #!/usr/bin/env bash
# set -euo pipefail

# # ===== FashionMNIST data check =====
# DATA_DIR="./data/FashionMNIST/raw"

# REQUIRED_FILES=(
#   "train-images-idx3-ubyte"
#   "train-labels-idx1-ubyte"
#   "t10k-images-idx3-ubyte"
#   "t10k-labels-idx1-ubyte"
# )

# echo "[INFO] Checking FashionMNIST dataset..."

# if [[ ! -d "${DATA_DIR}" ]]; then
#   echo "[WARRNING] ${DATA_DIR} does not exist."
#   echo "Run:"
#   cd data/FashionMNIST && bash ./download_data.sh
#   cd ../../
# fi

# MISSING=false
# for file in "${REQUIRED_FILES[@]}"; do
#   if [[ ! -f "${DATA_DIR}/${file}" ]]; then
#     echo "[MISSING] ${DATA_DIR}/${file}"
#     MISSING=true
#   fi
# done

# if [[ "${MISSING}" == true ]]; then
#   echo
#   echo "[ERROR] FashionMNIST dataset is incomplete."
#   echo "Please download it first:"
#   echo "  cd data/FashionMNIST && ./download_data.sh"
#   exit 1
# fi

# ls -al

# echo "[OK] FashionMNIST dataset found."

cp -r ../../../projects/DL ./course_data

docker build -t ghcr.io/amdresearch/auplc-dl:latest .

rm -rf ./course_data

