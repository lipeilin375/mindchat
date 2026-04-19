from app.services.emotion_service import EmotionInference


def main():
    # 方式1：使用默认模型路径 ../assets/tune_emotion.pt
    infer = EmotionInference()

    # 修改成你自己的音频路径
    audio_path = "./data/demo.wav"

    # 方式2：手动传入文本（跳过ASR）
    result = infer.predict(audio_path=audio_path, text="我今天真的很开心，状态特别好。")
    print("手动文本推理结果:")
    print(result)

    # 方式3：不传文本，自动ASR（需安装 faster-whisper）
    result_asr = infer.predict(audio_path=audio_path)
    print("\n自动ASR推理结果:")
    print(result_asr)


if __name__ == "__main__":
    main()
