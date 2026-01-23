<!-- Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved. -->
<!--
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
-->

# Large Language Model Labs

We provide a brief overview of the labs included in the `LLM` directory. Each lab focuses on a specific aspect of Large Language Model development and deployment, offering hands-on experience with key concepts and techniques from foundational deep learning to building complete transformer architectures.

## Lab Descriptions

### **LLM01: LLM Introduction and Inference**

- **Focus**: Getting started with Large Language Models
- **Key Learning**: Load pre-trained models, run text generation, adjust inference settings
- **Implementation**: Environment setup, Hugging Face model loading, prompt experimentation

### **LLM02: Deep Learning Basics**

- **Focus**: PyTorch fundamentals for LLM development
- **Key Learning**: Tensors, matrix operations, autograd basics, simple neural networks
- **Implementation**: Tensor operations, MLP construction, activation functions

### **LLM03: Neural Network Fundamentals**

- **Focus**: Core building blocks of neural networks
- **Key Learning**: Linear layers, weight matrices, broadcasting, matrix multiplication
- **Implementation**: Building linear transformations from scratch

### **LLM04: Tokenization and Text Processing**

- **Focus**: Converting text to numbers for neural networks
- **Key Learning**: Subword tokenization (BPE), padding/truncation, special tokens
- **Implementation**: Tokenizer comparison, sequence length analysis

### **LLM05a: Normalization Techniques**

- **Focus**: Normalization for stable training
- **Key Learning**: RMSNorm, positional encodings, GELU/SiLU activations, FFN design
- **Implementation**: Custom normalization layers, Pre-LN vs Post-LN comparison

### **LLM05b: Advanced Normalization Applications**

- **Focus**: Normalization in transformer architectures
- **Key Learning**: RMSNorm details, Pre-Norm stability, gradient flow effects
- **Implementation**: Stacking transformer blocks, exploring RoPE alternatives

### **LLM06: Attention Mechanisms**

- **Focus**: The core innovation behind transformers
- **Key Learning**: Q/K/V projections, scaled dot-product attention, causal masking, multi-head attention
- **Implementation**: Attention from scratch, visualization, cross-attention

### **LLM07: LoRA Fine-Tuning**

- **Focus**: Efficient fine-tuning with minimal parameters
- **Key Learning**: Low-rank decomposition, parameter freezing, rank/alpha selection
- **Implementation**: LoRA layer integration, gradient flow verification

### **LLM08: Dataset Processing and Training**

- **Focus**: Complete training pipeline
- **Key Learning**: Dataset loading, instruction formatting, data collation, training loops with mixed precision
- **Implementation**: Hugging Face Datasets, AdamW optimizer, gradient accumulation

### **LLM09: Custom Architectures**

- **Focus**: Building custom models with PyTorch
- **Key Learning**: nn.Module system, state management, model saving/loading
- **Implementation**: Custom CNN, LoRA integration, hybrid architectures

### **LLM10: Build a Tiny LLaMA from Scratch**

- **Focus**: Complete LLaMA-style transformer from scratch
- **Key Learning**: RMSNorm, RoPE, SwiGLU MLP, causal attention, weight tying
- **Implementation**: Full model assembly, training loop, text generation

## Lab Organization

The labs are organized progressively from foundational concepts to building complete language models:

**Introduction and Foundations (LLM01-LLM03)**: Getting started with LLMs and establishing deep learning fundamentals including tensor operations, automatic differentiation, and neural network building blocks essential for understanding transformer architectures.

**Text Processing and Normalization (LLM04-LLM05b)**: Core text processing techniques including tokenization strategies and normalization methods (Layer Norm, RMSNorm) that are critical for stable and efficient transformer training.

**Attention and Efficiency (LLM06-LLM07)**: The heart of transformer models with comprehensive coverage of attention mechanisms and parameter-efficient fine-tuning techniques like LoRA for adapting models with minimal resources.

**Training and Architecture (LLM08-LLM10)**: Complete end-to-end workflows for dataset processing, model training, custom architecture design, and culminating in building a fully functional LLaMA-style model from scratch.
