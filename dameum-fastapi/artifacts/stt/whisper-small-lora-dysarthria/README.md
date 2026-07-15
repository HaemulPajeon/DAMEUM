---
base_model: openai/whisper-small
library_name: peft
tags:
- base_model:adapter:openai/whisper-small
- lora
- transformers
- automatic-speech-recognition
language:
- ko
---

# whisper-small-lora-dysarthria

LoRA adapter for `openai/whisper-small`, fine-tuned on Korean dysarthric (구음장애/마비말장애) speech from the AI-Hub `013.구음장애 음성인식 데이터` corpus (뇌신경장애 subset). See `../../README.md` (stt-lora project root) for the full pipeline, data caveats, and results.

## Results

CER on held-out test clips (n=125): zero-shot whisper-small 64.3% → this adapter 53.6%.

This is a prototype trained on a small subset (24 min train / 14 min val / 12 min test) due to hackathon time constraints, not a production-accuracy model.

## Training

- LoRA: r=32, alpha=64, dropout=0.05, target_modules=[q_proj, v_proj]
- lr=1e-4, warmup=6 steps, max_steps=60 (~3 epochs), batch=4, grad_accum=4, fp16, gradient_checkpointing
- Trainable params: 3,538,944 / 245,273,856 (1.44%)

### Framework versions

- PEFT 0.19.1
