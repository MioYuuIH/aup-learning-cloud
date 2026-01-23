#!/bin/bash
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

# ====================================================================
# IMPORTANT: Modify node names below to match your cluster
# Run 'kubectl get nodes' to see your actual node names
# ====================================================================

# Label nodes
kubectl label nodes phx-1 node-type=phx
kubectl label nodes phx-64g node-type=phx
kubectl label nodes rdna4-1 node-type=dgpu
kubectl label nodes strix-1 node-type=strix
kubectl label nodes strix-2 node-type=strix
kubectl label nodes strix-3 node-type=strix
kubectl label nodes strix-4 node-type=strix
kubectl label nodes strix-5 node-type=strix
kubectl label nodes strix-6 node-type=strix
kubectl label nodes strix-7 node-type=strix
kubectl label nodes strix-halo-1 node-type=strix-halo
kubectl label nodes strix-halo-2 node-type=strix-halo
kubectl label nodes strix-halo-3 node-type=strix-halo
kubectl label nodes strix-halo-4 node-type=strix-halo

# Verify labels
kubectl get nodes --show-labels

