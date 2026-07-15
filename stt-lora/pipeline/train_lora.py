"""S5: LoRA fine-tune whisper-small on the dysarthria clip manifests.
Config follows the agreed handoff-doc defaults, batch/accum sized for the
local 8GB RTX 4070 Laptop GPU (see plan: batch=4, grad_accum=4, fp16,
gradient_checkpointing)."""
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import librosa
import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    WhisperForConditionalGeneration,
    WhisperProcessor,
)

# Point DAMEUM_STT_DATA_DIR at your local copy of the AI-Hub data + manifests
# (not checked into git -- see stt-lora/README.md for how to regenerate it).
_DATA_DIR = Path(os.environ.get("DAMEUM_STT_DATA_DIR", "./data"))
MANIFEST_DIR = _DATA_DIR / "manifests"
# Training writes here by default (NOT the repo's committed adapter under
# ../outputs/) so a re-run never clobbers the checked-in one; copy it over
# manually if the retrain is actually better.
OUTPUT_DIR = _DATA_DIR / "outputs" / "whisper-small-lora-dysarthria"
MODEL_ID = "openai/whisper-small"

BATCH_SIZE = 4
GRAD_ACCUM = 4
# LR=1e-3 caused a gradient-norm blowup (peaked at 705) around step 35 that the
# model never recovered from -- by step 150 (~8 epochs over just 294 clips) it
# had collapsed to predicting "." for every input (WER=1.0). Dropped 10x and
# capped steps to roughly 3 epochs instead of 8 to stop it from overfitting/
# collapsing on this very small dataset; added warmup to avoid an early spike.
LR = 1e-4
EPOCHS = 3
MAX_STEPS = 60
WARMUP_STEPS = 6


def load_split(split):
    rows = [json.loads(l) for l in open(MANIFEST_DIR / f"manifest_{split}.jsonl", encoding="utf-8")]
    return Dataset.from_list([{"audio_path": r["clip_path"], "text": r["gt_text"]} for r in rows])


@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    processor: Any

    def __call__(self, features):
        input_features = [{"input_features": f["input_features"]} for f in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")
        labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
            labels = labels[:, 1:]
        batch["labels"] = labels
        return batch


def main():
    processor = WhisperProcessor.from_pretrained(MODEL_ID, language="korean", task="transcribe")

    def prepare(batch):
        audio, _ = librosa.load(batch["audio_path"], sr=16000, mono=True)
        batch["input_features"] = processor.feature_extractor(
            audio, sampling_rate=16000
        ).input_features[0]
        batch["labels"] = processor.tokenizer(batch["text"]).input_ids
        return batch

    train_ds = load_split("train").map(prepare, remove_columns=["audio_path", "text"])
    val_ds = load_split("val").map(prepare, remove_columns=["audio_path", "text"])
    print(f"train={len(train_ds)} clips, val={len(val_ds)} clips")

    model = WhisperForConditionalGeneration.from_pretrained(MODEL_ID)
    model.generation_config.language = "korean"
    model.generation_config.task = "transcribe"
    model.generation_config.forced_decoder_ids = None
    model.config.use_cache = False  # required alongside gradient checkpointing

    lora_config = LoraConfig(
        r=32, lora_alpha=64, target_modules=["q_proj", "v_proj"], lora_dropout=0.05, bias="none"
    )
    model = get_peft_model(model, lora_config)
    model.enable_input_require_grads()
    model.print_trainable_parameters()

    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)

    args = Seq2SeqTrainingArguments(
        output_dir=str(OUTPUT_DIR),
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        per_device_eval_batch_size=BATCH_SIZE,
        learning_rate=LR,
        warmup_steps=WARMUP_STEPS,
        num_train_epochs=EPOCHS,
        max_steps=MAX_STEPS,
        fp16=torch.cuda.is_available(),
        gradient_checkpointing=True,
        eval_strategy="no",  # skip mid-train generation-based eval to save time; evaluate.py does the real S6 pass
        save_strategy="no",
        predict_with_generate=True,
        generation_max_length=225,
        logging_steps=5,
        remove_unused_columns=False,
        label_names=["labels"],
        report_to=[],
    )

    trainer = Seq2SeqTrainer(
        args=args,
        model=model,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=data_collator,
        processing_class=processor.feature_extractor,
    )

    trainer.train()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUTPUT_DIR))
    processor.save_pretrained(str(OUTPUT_DIR))
    print(f"Adapter saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
