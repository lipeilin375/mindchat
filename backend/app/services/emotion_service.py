"""
中文音频情绪识别 - 双流融合模型训练脚本
架构：音频特征(BiLSTM) + ASR文本(BERT) → Cross-Attention融合 → 情绪分类

支持数据集：CASIA / MELD-CN / 自定义数据集
情绪类别（默认6类）：angry, disgust, fear, happy, neutral, sad
"""

import os
import json
import logging
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.metrics import classification_report, confusion_matrix
from tqdm import tqdm

import librosa
import soundfile as sf
from transformers import BertTokenizer, BertModel, get_linear_schedule_with_warmup

# ── 可选：faster-whisper ASR（若未安装则跳过，直接用标注文本）
try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False
    print("[WARN] faster-whisper 未安装，将使用数据集自带文本标注")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# 1. 配置
# ════════════════════════════════════════════════════════════

@dataclass
class TrainConfig:
    # 数据
    data_root: str = "./data"                    # 数据集根目录
    label_file: str = "./data/labels.json"       # {"audio_path": "...", "text": "...", "label": 0}
    output_dir: str = "./checkpoints"
    num_classes: int = 6
    label_names: List[str] = field(default_factory=lambda: [
        "angry", "disgust", "fear", "happy", "neutral", "sad"
    ])

    # 音频特征
    sample_rate: int = 16000
    max_audio_len: int = 6                       # 秒
    n_mfcc: int = 40
    n_mels: int = 80
    hop_length: int = 160                        # 10ms @ 16kHz
    win_length: int = 400                        # 25ms @ 16kHz
    use_delta: bool = True                       # 追加一阶/二阶差分

    # 文本
    bert_model: str = "bert-base-chinese"
    max_text_len: int = 128

    # ASR
    whisper_model: str = "small"                 # tiny/small/medium
    whisper_device: str = "cpu"
    # whisper_device: str = "cuda"
    asr_cache_file: str = "./data/asr_cache.json"

    # 模型超参
    audio_hidden: int = 256                      # BiLSTM hidden size
    audio_layers: int = 2
    audio_dropout: float = 0.3
    bert_hidden: int = 768
    fusion_dim: int = 512
    fusion_heads: int = 8
    fusion_dropout: float = 0.2
    classifier_hidden: int = 256

    # 训练
    epochs: int = 30
    batch_size: int = 16
    lr_bert: float = 2e-5
    lr_other: float = 1e-3
    weight_decay: float = 1e-4
    warmup_ratio: float = 0.1
    grad_clip: float = 1.0
    val_ratio: float = 0.15
    test_ratio: float = 0.10
    seed: int = 42
    num_workers: int = 4
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    # 损失
    use_label_smoothing: bool = True
    label_smoothing: float = 0.1
    use_class_weights: bool = True              # 处理类别不平衡


# ════════════════════════════════════════════════════════════
# 2. 音频特征提取
# ════════════════════════════════════════════════════════════

class AudioFeatureExtractor:
    """提取 MFCC + Mel + Chroma + ZCR + RMS，拼接后返回 (T, feature_dim)"""

    def __init__(self, cfg: TrainConfig):
        self.cfg = cfg
        self.max_frames = int(cfg.max_audio_len * cfg.sample_rate / cfg.hop_length) + 1

    def extract(self, audio_path: str) -> np.ndarray:
        # 加载并统一采样率
        try:
            y, sr = librosa.load(audio_path, sr=self.cfg.sample_rate, mono=True)
        except Exception as e:
            logger.warning(f"加载音频失败 {audio_path}: {e}，使用零向量")
            return np.zeros((self.max_frames, self._feature_dim()), dtype=np.float32)

        # 裁剪 / 填充
        max_samples = self.cfg.max_audio_len * self.cfg.sample_rate
        if len(y) > max_samples:
            y = y[:max_samples]
        else:
            y = np.pad(y, (0, max_samples - len(y)))

        kw = dict(sr=self.cfg.sample_rate, hop_length=self.cfg.hop_length,
                  win_length=self.cfg.win_length)

        # MFCC (40)
        mfcc = librosa.feature.mfcc(y=y, n_mfcc=self.cfg.n_mfcc, **kw)  # (40, T)
        features = [mfcc]

        if self.cfg.use_delta:
            features.append(librosa.feature.delta(mfcc))        # Δ MFCC
            features.append(librosa.feature.delta(mfcc, order=2))  # ΔΔ MFCC

        # Mel (80)
        mel = librosa.feature.melspectrogram(y=y, n_mels=self.cfg.n_mels, **kw)
        mel_db = librosa.power_to_db(mel, ref=np.max)
        features.append(mel_db)

        # Chroma (12)
        chroma = librosa.feature.chroma_stft(y=y, **kw)
        features.append(chroma)

        # ZCR (1) + RMS (1)
        zcr = librosa.feature.zero_crossing_rate(y, hop_length=self.cfg.hop_length)
        rms = librosa.feature.rms(y=y, hop_length=self.cfg.hop_length)
        features.extend([zcr, rms])

        # 拼接 → (feature_dim, T)
        feat = np.concatenate(features, axis=0)  # (D, T)

        # 截断/填充到固定 T
        T = feat.shape[1]
        if T > self.max_frames:
            feat = feat[:, :self.max_frames]
        else:
            feat = np.pad(feat, ((0, 0), (0, self.max_frames - T)))

        # 标准化（每特征维度）
        mean = feat.mean(axis=1, keepdims=True)
        std  = feat.std(axis=1, keepdims=True) + 1e-6
        feat = (feat - mean) / std

        return feat.T.astype(np.float32)  # (T, D)

    def _feature_dim(self) -> int:
        base = self.cfg.n_mfcc
        if self.cfg.use_delta:
            base *= 3
        return base + self.cfg.n_mels + 12 + 2  # +chroma +zcr+rms


# ════════════════════════════════════════════════════════════
# 3. ASR 转录（带缓存）
# ════════════════════════════════════════════════════════════

class ASRTranscriber:
    """使用 faster-whisper 对音频批量转录，结果缓存到 JSON"""

    def __init__(self, cfg: TrainConfig):
        self.cfg = cfg
        self.cache: Dict[str, str] = {}
        if os.path.exists(cfg.asr_cache_file):
            with open(cfg.asr_cache_file, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
            logger.info(f"已加载 ASR 缓存 ({len(self.cache)} 条)")

        if HAS_WHISPER:
            logger.info(f"加载 Whisper {cfg.whisper_model} ...")
            self.model = WhisperModel(cfg.whisper_model)
        else:
            self.model = None

    def transcribe(self, audio_path: str) -> str:
        if audio_path in self.cache:
            return self.cache[audio_path]
        if self.model is None:
            return ""
        segments, _ = self.model.transcribe(audio_path, language="zh", beam_size=5)
        text = "".join(seg.text for seg in segments).strip()
        self.cache[audio_path] = text
        return text

    def save_cache(self):
        os.makedirs(os.path.dirname(self.cfg.asr_cache_file) or ".", exist_ok=True)
        with open(self.cfg.asr_cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
        logger.info(f"ASR 缓存已保存 ({len(self.cache)} 条)")


# ════════════════════════════════════════════════════════════
# 4. 数据集
# ════════════════════════════════════════════════════════════

class EmotionDataset(Dataset):
    """
    label_file 格式（JSON 列表）:
    [
      {"audio_path": "path/to/wav", "text": "可选文本", "label": 0},
      ...
    ]
    若 text 为空字符串，则由 ASR 自动转录
    """

    def __init__(
        self,
        samples: List[dict],
        audio_extractor: AudioFeatureExtractor,
        tokenizer: BertTokenizer,
        asr: Optional[ASRTranscriber],
        cfg: TrainConfig
    ):
        self.samples = samples
        self.audio_ext = audio_extractor
        self.tokenizer = tokenizer
        self.asr = asr
        self.cfg = cfg

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        item = self.samples[idx]
        audio_path = item["audio_path"]
        label = int(item["label"])

        # ── 音频特征
        audio_feat = self.audio_ext.extract(audio_path)  # (T, D)

        # ── 文本（优先使用标注，否则 ASR）
        text = item.get("text", "").strip()
        if not text and self.asr is not None:
            text = self.asr.transcribe(audio_path)
        if not text:
            text = "无"  # fallback，避免空输入

        # ── BERT 编码
        enc = self.tokenizer(
            text,
            max_length=self.cfg.max_text_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        return {
            "audio_feat":   torch.tensor(audio_feat, dtype=torch.float32),
            "input_ids":    enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "token_type_ids": enc["token_type_ids"].squeeze(0),
            "label":        torch.tensor(label, dtype=torch.long),
        }


# ════════════════════════════════════════════════════════════
# 5. 模型
# ════════════════════════════════════════════════════════════

class AudioEncoder(nn.Module):
    """BiLSTM 编码音频序列 → 上下文表示"""

    def __init__(self, input_dim: int, cfg: TrainConfig):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=cfg.audio_hidden,
            num_layers=cfg.audio_layers,
            batch_first=True,
            bidirectional=True,
            dropout=cfg.audio_dropout if cfg.audio_layers > 1 else 0.0
        )
        self.layer_norm = nn.LayerNorm(cfg.audio_hidden * 2)
        self.dropout = nn.Dropout(cfg.audio_dropout)
        self.out_dim = cfg.audio_hidden * 2

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        # x: (B, T, D)
        out, (h, _) = self.lstm(x)           # out: (B, T, 2H)
        out = self.layer_norm(out)
        out = self.dropout(out)
        # 取最后一层双向 hidden 拼接作为 sentence-level 向量
        h_last = torch.cat([h[-2], h[-1]], dim=-1)  # (B, 2H)
        return out, h_last                    # 序列表示 + 全局表示


class CrossModalAttention(nn.Module):
    """Query=音频全局向量，Key/Value=BERT token序列 → 文本引导的音频-文本对齐"""

    def __init__(self, audio_dim: int, text_dim: int, fusion_dim: int, n_heads: int):
        super().__init__()
        self.proj_q = nn.Linear(audio_dim, fusion_dim)
        self.proj_k = nn.Linear(text_dim,  fusion_dim)
        self.proj_v = nn.Linear(text_dim,  fusion_dim)
        self.attn   = nn.MultiheadAttention(fusion_dim, n_heads, batch_first=True)
        self.norm   = nn.LayerNorm(fusion_dim)

    def forward(
        self,
        audio_global: torch.Tensor,    # (B, audio_dim)
        text_seq: torch.Tensor,        # (B, L, text_dim)
        key_padding_mask: Optional[torch.Tensor] = None  # (B, L) True=ignore
    ) -> torch.Tensor:
        q = self.proj_q(audio_global).unsqueeze(1)   # (B, 1, F)
        k = self.proj_k(text_seq)                     # (B, L, F)
        v = self.proj_v(text_seq)                     # (B, L, F)
        attn_out, _ = self.attn(q, k, v, key_padding_mask=key_padding_mask)
        return self.norm(attn_out.squeeze(1))          # (B, F)


class DualStreamFusionModel(nn.Module):
    """
    双流融合情绪识别模型
    - Stream A: 音频 BiLSTM
    - Stream B: BERT
    - Fusion: Cross-Attention + 拼接 + MLP
    """

    def __init__(self, audio_input_dim: int, cfg: TrainConfig):
        super().__init__()
        self.cfg = cfg

        # 音频流
        self.audio_enc = AudioEncoder(audio_input_dim, cfg)

        # 文本流（冻结底部 8 层，微调顶部 4 层）
        self.bert = BertModel.from_pretrained(cfg.bert_model)
        self._freeze_bert_layers(freeze_until=8)

        # 跨模态注意力（音频 query → 文本 key/value）
        self.cross_attn = CrossModalAttention(
            audio_dim=self.audio_enc.out_dim,
            text_dim=cfg.bert_hidden,
            fusion_dim=cfg.fusion_dim,
            n_heads=cfg.fusion_heads
        )

        # 反向跨模态（文本 query → 音频 sequence）
        self.cross_attn_rev = CrossModalAttention(
            audio_dim=cfg.bert_hidden,
            text_dim=self.audio_enc.out_dim,
            fusion_dim=cfg.fusion_dim,
            n_heads=cfg.fusion_heads
        )

        # 门控融合
        total_dim = self.audio_enc.out_dim + cfg.bert_hidden + cfg.fusion_dim * 2
        self.gate = nn.Sequential(
            nn.Linear(total_dim, total_dim),
            nn.Sigmoid()
        )

        # 分类头
        self.classifier = nn.Sequential(
            nn.Linear(total_dim, cfg.classifier_hidden),
            nn.GELU(),
            nn.Dropout(cfg.fusion_dropout),
            nn.LayerNorm(cfg.classifier_hidden),
            nn.Linear(cfg.classifier_hidden, cfg.num_classes)
        )

    def _freeze_bert_layers(self, freeze_until: int):
        for name, param in self.bert.named_parameters():
            # 解析层号
            if "encoder.layer." in name:
                layer_num = int(name.split("encoder.layer.")[1].split(".")[0])
                if layer_num < freeze_until:
                    param.requires_grad = False
            elif "embeddings" in name:
                param.requires_grad = False

    def forward(self, batch: dict) -> torch.Tensor:
        audio_feat    = batch["audio_feat"]       # (B, T, D)
        input_ids     = batch["input_ids"]        # (B, L)
        attention_mask = batch["attention_mask"]  # (B, L)
        token_type_ids = batch["token_type_ids"]  # (B, L)

        # ── 音频编码
        audio_seq, audio_global = self.audio_enc(audio_feat)  # (B,T,2H), (B,2H)

        # ── 文本编码
        bert_out = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids
        )
        text_seq   = bert_out.last_hidden_state   # (B, L, 768)
        text_global = bert_out.pooler_output      # (B, 768)

        # ── 跨模态注意力
        key_pad_mask = (attention_mask == 0)       # True = padding
        fused_a2t = self.cross_attn(audio_global, text_seq, key_pad_mask)    # (B, F)
        fused_t2a = self.cross_attn_rev(text_global, audio_seq)              # (B, F)

        # ── 门控拼接
        concat = torch.cat([audio_global, text_global, fused_a2t, fused_t2a], dim=-1)
        gate   = self.gate(concat)
        fused  = concat * gate

        return self.classifier(fused)  # (B, num_classes)


# ════════════════════════════════════════════════════════════
# 6. 训练工具
# ════════════════════════════════════════════════════════════

class LabelSmoothingCE(nn.Module):
    def __init__(self, num_classes: int, smoothing: float = 0.1,
                 weight: Optional[torch.Tensor] = None):
        super().__init__()
        self.smoothing = smoothing
        self.num_classes = num_classes
        self.weight = weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        log_prob = F.log_softmax(logits, dim=-1)
        smooth_val = self.smoothing / (self.num_classes - 1)
        one_hot = torch.full_like(log_prob, smooth_val)
        one_hot.scatter_(1, targets.unsqueeze(1), 1.0 - self.smoothing)
        loss = -(one_hot * log_prob)
        if self.weight is not None:
            loss = loss * self.weight.unsqueeze(0)
        return loss.sum(dim=-1).mean()


def compute_class_weights(samples: List[dict], num_classes: int) -> torch.Tensor:
    counts = np.zeros(num_classes)
    for s in samples:
        counts[int(s["label"])] += 1
    weights = counts.sum() / (num_classes * (counts + 1e-6))
    return torch.tensor(weights, dtype=torch.float32)


def evaluate(model, loader, criterion, device) -> Tuple[float, float, dict]:
    model.eval()
    total_loss, correct, total = 0., 0, 0
    all_preds, all_labels = [], []

    with torch.no_grad():
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            logits = model(batch)
            loss   = criterion(logits, batch["label"])
            preds  = logits.argmax(dim=-1)

            total_loss += loss.item() * len(batch["label"])
            correct    += (preds == batch["label"]).sum().item()
            total      += len(batch["label"])
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(batch["label"].cpu().tolist())

    report = classification_report(all_labels, all_preds, output_dict=True, zero_division=0)
    return total_loss / total, correct / total, report


# ════════════════════════════════════════════════════════════
# 7. 主训练流程
# ════════════════════════════════════════════════════════════

def train(cfg: TrainConfig):
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    os.makedirs(cfg.output_dir, exist_ok=True)
    device = torch.device(cfg.device)
    logger.info(f"使用设备: {device}")

    # ── 加载标注
    with open(cfg.label_file, "r", encoding="utf-8") as f:
        all_samples = json.load(f)
    logger.info(f"总样本数: {len(all_samples)}")

    # 数据集拆分
    np.random.shuffle(all_samples)
    n_test  = int(len(all_samples) * cfg.test_ratio)
    n_val   = int(len(all_samples) * cfg.val_ratio)
    test_s  = all_samples[:n_test]
    val_s   = all_samples[n_test:n_test + n_val]
    train_s = all_samples[n_test + n_val:]
    logger.info(f"Train/Val/Test: {len(train_s)}/{len(val_s)}/{len(test_s)}")

    # ── 组件初始化
    audio_ext = AudioFeatureExtractor(cfg)
    audio_dim  = audio_ext._feature_dim()
    logger.info(f"音频特征维度: {audio_dim}")

    tokenizer = BertTokenizer.from_pretrained(cfg.bert_model)

    asr = None
    if HAS_WHISPER:
        asr = ASRTranscriber(cfg)

    # ── 数据集 & DataLoader
    def make_loader(samples, shuffle):
        ds = EmotionDataset(samples, audio_ext, tokenizer, asr, cfg)
        # WhisperModel (ctranslate2) 对象不可被 pickle，在 Windows 的多进程
        # DataLoader 中会触发 TypeError: cannot pickle 'ctranslate2._ext.Whisper'.
        # 避免将 ASR 模型跨进程传递，检测到 ASR 启用时强制使用单进程加载。
        num_workers = 0 if asr is not None else cfg.num_workers
        return DataLoader(ds, batch_size=cfg.batch_size, shuffle=shuffle,
                          num_workers=num_workers, pin_memory=True)

    train_loader = make_loader(train_s, shuffle=True)
    val_loader   = make_loader(val_s,   shuffle=False)
    test_loader  = make_loader(test_s,  shuffle=False)

    # ── 模型
    model = DualStreamFusionModel(audio_dim, cfg).to(device)
    total_params = sum(p.numel() for p in model.parameters())
    trainable    = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"模型参数: 总计 {total_params:,} | 可训练 {trainable:,}")

    # ── 损失函数
    class_weights = None
    if cfg.use_class_weights:
        class_weights = compute_class_weights(train_s, cfg.num_classes).to(device)
        logger.info(f"类别权重: {class_weights.cpu().numpy().round(3)}")

    criterion = (LabelSmoothingCE(cfg.num_classes, cfg.label_smoothing, class_weights)
                 if cfg.use_label_smoothing
                 else nn.CrossEntropyLoss(weight=class_weights))

    # ── 差分学习率优化器
    bert_params  = list(model.bert.parameters())
    other_params = [p for p in model.parameters()
                    if not any(p is bp for bp in bert_params)]
    optimizer = AdamW([
        {"params": bert_params,  "lr": cfg.lr_bert,  "weight_decay": 0.01},
        {"params": other_params, "lr": cfg.lr_other, "weight_decay": cfg.weight_decay},
    ])

    total_steps   = len(train_loader) * cfg.epochs
    warmup_steps  = int(total_steps * cfg.warmup_ratio)
    scheduler     = get_linear_schedule_with_warmup(
        optimizer, warmup_steps, total_steps
    )

    # ── 训练循环
    best_val_f1 = 0.0
    best_ckpt   = os.path.join(cfg.output_dir, "best_model.pt")
    history     = {"train_loss": [], "val_loss": [], "val_acc": [], "val_f1": []}

    for epoch in range(1, cfg.epochs + 1):
        model.train()
        epoch_loss, epoch_correct, epoch_total = 0., 0, 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch:02d}/{cfg.epochs}", leave=False)
        for batch in pbar:
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad()
            logits = model(batch)
            loss   = criterion(logits, batch["label"])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            optimizer.step()
            scheduler.step()

            bs = len(batch["label"])
            epoch_loss    += loss.item() * bs
            epoch_correct += (logits.argmax(-1) == batch["label"]).sum().item()
            epoch_total   += bs
            pbar.set_postfix(loss=f"{loss.item():.4f}")

        train_loss = epoch_loss / epoch_total
        train_acc  = epoch_correct / epoch_total

        val_loss, val_acc, val_report = evaluate(model, val_loader, criterion, device)
        val_f1 = val_report["macro avg"]["f1-score"]

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        history["val_f1"].append(val_f1)

        logger.info(
            f"Epoch {epoch:02d} | "
            f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
            f"Val Loss: {val_loss:.4f} Acc: {val_acc:.4f} F1: {val_f1:.4f}"
        )

        # 保存最优
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            torch.save({
                "epoch": epoch,
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "val_f1": val_f1,
                "cfg": cfg.__dict__,
                "audio_dim": audio_dim,
            }, best_ckpt)
            logger.info(f"  ✓ 保存最优模型 (Val F1: {best_val_f1:.4f})")

    # ── 测试集评估
    logger.info("\n══ 测试集评估 ══")
    ckpt = torch.load(best_ckpt, map_location=device)
    model.load_state_dict(ckpt["model_state"])
    test_loss, test_acc, test_report = evaluate(model, test_loader, criterion, device)
    logger.info(f"Test Loss: {test_loss:.4f} | Test Acc: {test_acc:.4f}")
    logger.info("\n" + classification_report(
        [s["label"] for s in test_s],
        [],  # placeholder, 实际在 evaluate 内已计算
        target_names=cfg.label_names[:cfg.num_classes],
        zero_division=0
    ) if False else "")  # 正式结果已在 evaluate 内打印
    logger.info(f"\n分类报告:\n{json.dumps(test_report, indent=2, ensure_ascii=False)}")

    # 保存历史
    with open(os.path.join(cfg.output_dir, "history.json"), "w") as f:
        json.dump(history, f, indent=2)

    # 保存 ASR 缓存
    if asr:
        asr.save_cache()

    logger.info(f"\n训练完成！最优 Val F1: {best_val_f1:.4f}")
    logger.info(f"最优模型已保存到: {best_ckpt}")


# ════════════════════════════════════════════════════════════
# 8. 推理接口
# ════════════════════════════════════════════════════════════

class EmotionInference:
    """单文件推理，加载训练好的模型"""

    def __init__(self, ckpt_path: str, device: str = "cpu"):
        ckpt = torch.load(ckpt_path, map_location=device)
        self.cfg = TrainConfig(**{k: v for k, v in ckpt["cfg"].items()
                                  if k in TrainConfig.__dataclass_fields__})
        self.cfg.device = device
        self.device = torch.device(device)

        audio_dim = ckpt["audio_dim"]
        self.model = DualStreamFusionModel(audio_dim, self.cfg).to(self.device)
        self.model.load_state_dict(ckpt["model_state"])
        self.model.eval()

        self.audio_ext = AudioFeatureExtractor(self.cfg)
        self.tokenizer = BertTokenizer.from_pretrained(self.cfg.bert_model)
        self.asr = ASRTranscriber(self.cfg) if HAS_WHISPER else None

    @torch.no_grad()
    def predict(self, audio_path: str, text: Optional[str] = None) -> dict:
        if text is None:
            text = self.asr.transcribe(audio_path) if self.asr else "无"

        audio_feat = torch.tensor(
            self.audio_ext.extract(audio_path), dtype=torch.float32
        ).unsqueeze(0).to(self.device)

        enc = self.tokenizer(
            text, max_length=self.cfg.max_text_len,
            padding="max_length", truncation=True, return_tensors="pt"
        )
        batch = {
            "audio_feat":    audio_feat,
            "input_ids":     enc["input_ids"].to(self.device),
            "attention_mask": enc["attention_mask"].to(self.device),
            "token_type_ids": enc["token_type_ids"].to(self.device),
        }
        logits = self.model(batch)
        probs  = F.softmax(logits, dim=-1)[0].cpu().tolist()
        pred   = int(logits.argmax(-1).item())

        return {
            "label":       pred,
            "emotion":     self.cfg.label_names[pred],
            "confidence":  max(probs),
            "probs":       {n: round(p, 4) for n, p in
                            zip(self.cfg.label_names, probs)},
            "asr_text":    text,
        }


# ════════════════════════════════════════════════════════════
# 9. 入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="中文音频情绪识别训练")
    parser.add_argument("--data_root",   default="./data")
    parser.add_argument("--label_file",  default="./data/labels.json")
    parser.add_argument("--output_dir",  default="./checkpoints")
    parser.add_argument("--bert_model",  default="bert-base-chinese")
    parser.add_argument("--epochs",      type=int,   default=30)
    parser.add_argument("--batch_size",  type=int,   default=16)
    parser.add_argument("--num_classes", type=int,   default=6)
    parser.add_argument("--whisper_model", default="small")
    parser.add_argument("--device",      default="cpu" if not torch.cuda.is_available() else "gpu")
    # 推理模式
    parser.add_argument("--infer",       action="store_true")
    parser.add_argument("--ckpt",        default="./checkpoints/best_model.pt")
    parser.add_argument("--audio",       default=None)
    args = parser.parse_args()

    if args.infer:
        inf = EmotionInference(args.ckpt, device=args.device)
        result = inf.predict(args.audio)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        cfg = TrainConfig(
            data_root=args.data_root,
            label_file=args.label_file,
            output_dir=args.output_dir,
            bert_model=args.bert_model,
            epochs=args.epochs,
            batch_size=args.batch_size,
            num_classes=args.num_classes,
            whisper_model=args.whisper_model,
            device=args.device,
        )
        train(cfg)
