const recordBtn = document.getElementById('recordingBtn');
const statusMsgSpan = document.getElementById('statusMsg');
var token = localStorage.getItem('mindchat_token');

// 录音相关变量
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let stream = null;

// 音频上下文 (用于重采样至16kHz)
let audioContext = null;

// 配置参数
const TARGET_SAMPLE_RATE = 16000;      // 16kHz
const UPLOAD_URL = `${base_url}/api/analysis/upload`;

// 辅助函数：更新状态提示
function updateStatus(message, isError = false, isLoading = false) {
    if (!statusMsgSpan) return;
    if (isLoading) {
        statusMsgSpan.innerHTML = `<span class="upload-loading"></span> ${message}`;
    } else {
        statusMsgSpan.innerHTML = message;
        statusMsgSpan.style.color = isError ? '#dc3545' : '#28a745';
        if (!isError && message.includes('成功')) {
            // 成功提示3秒后恢复默认颜色
            setTimeout(() => {
                if (statusMsgSpan && !statusMsgSpan.innerHTML.includes('上传成功')) return;
                statusMsgSpan.style.color = '';
            }, 3000);
        } else if (isError) {
            setTimeout(() => {
                if (statusMsgSpan && statusMsgSpan.innerHTML === message) {
                    statusMsgSpan.style.color = '';
                }
            }, 4000);
        }
    }
}

// 重置按钮UI为闲置状态
function resetButtonUI() {
    if (!recordBtn) return;
    recordBtn.classList.remove('recording');
    const iconSpan = recordBtn.querySelector('.mdi');
    const textSpan = recordBtn.querySelector('.btn-text');
    if (iconSpan) iconSpan.className = 'mdi mdi-microphone';
    if (textSpan) textSpan.innerText = '开始录音';
    recordBtn.disabled = false;
}

// 设置为录音中UI
function setRecordingUI() {
    if (!recordBtn) return;
    recordBtn.classList.add('recording');
    const iconSpan = recordBtn.querySelector('.mdi');
    const textSpan = recordBtn.querySelector('.btn-text');
    if (iconSpan) iconSpan.className = 'mdi mdi-stop-circle';
    if (textSpan) textSpan.innerText = '停止录音';
    recordBtn.disabled = false;
}

// 将 AudioBuffer 重采样到 targetSampleRate (16kHz)
async function resampleAudioBuffer(sourceBuffer, targetRate) {
    const sourceRate = sourceBuffer.sampleRate;
    if (sourceRate === targetRate) {
        return sourceBuffer;
    }
    // 创建离线上下文，目标采样率 targetRate，单声道
    const duration = sourceBuffer.duration;
    const offlineCtx = new OfflineAudioContext(
        1,  // 单声道输出
        duration * targetRate,
        targetRate
    );
    // 创建音频源
    const source = offlineCtx.createBufferSource();
    source.buffer = sourceBuffer;
    source.connect(offlineCtx.destination);
    source.start();
    // 渲染重采样后的 buffer
    const renderedBuffer = await offlineCtx.startRendering();
    return renderedBuffer;
}

// 将 AudioBuffer 转换为 WAV 格式 Blob (16-bit PCM, 小端)
function bufferToWav(audioBuffer) {
    const numberOfChannels = audioBuffer.numberOfChannels;
    const sampleRate = audioBuffer.sampleRate;
    const format = 1; // PCM
    const bitDepth = 16;

    let samples = audioBuffer.getChannelData(0); // 取第一声道
    // 将浮点数 (-1..1) 转换为 16-bit int
    const dataLength = samples.length * (bitDepth / 8);
    const buffer = new ArrayBuffer(44 + dataLength);
    const view = new DataView(buffer);

    // 写 WAV 头
    // RIFF chunk
    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataLength, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true); // fmt 块大小
    view.setUint16(20, format, true); // PCM
    view.setUint16(22, numberOfChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numberOfChannels * (bitDepth / 8), true); // 字节率
    view.setUint16(32, numberOfChannels * (bitDepth / 8), true); // 块对齐
    view.setUint16(34, bitDepth, true);
    writeString(view, 36, 'data');
    view.setUint32(40, dataLength, true);

    // 写入样本数据
    let offset = 44;
    for (let i = 0; i < samples.length; i++) {
        const sample = Math.max(-1, Math.min(1, samples[i]));
        const intSample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        view.setInt16(offset, intSample, true);
        offset += 2;
    }
    return new Blob([buffer], { type: 'audio/wav' });
}

function writeString(view, offset, str) {
    for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
    }
}

// 上传录音文件 (Blob)
async function uploadAudioBlob(wavBlob) {
    const formData = new FormData();
    // 文件名带上时间戳，便于后端识别
    const fileName = `recording_${Date.now()}.wav`;
    formData.append('file', wavBlob, fileName);

    updateStatus('📤 正在上传音频文件并分析情绪...', false, true);

    try {
        const response = await fetch(UPLOAD_URL, {
            method: 'POST',
            body: formData,
            headers: {
                'Authorization': 'Bearer ' + token
            }
        });

        if (!response.ok) {
            let errorMsg = `上传失败 (${response.status})`;
            try {
                const errData = await response.json();
                errorMsg = errData.detail;
            } catch (e) { }
            throw new Error(errorMsg);
        }

        const result = await response.json();
        let successMsg = '✅ 分析完成！';
        
        updateStatus(successMsg, false);
        if (typeof $.notify === 'function') {
            $.notify({
                message: successMsg,
                icon: 'mdi mdi-emoticon-happy'
            }, {
                type: 'success',
                delay: 3000
            });
        }
    } catch (error) {
        console.error('上传失败:', error);
        updateStatus(`❌ 上传或分析失败: ${error.detail}`, true);
        if (typeof $.notify === 'function') {
            $.notify({
                message: `上传失败: ${error.detail}`,
                icon: 'mdi mdi-alert'
            }, {
                type: 'danger',
                delay: 4000
            });
        }
    }
}

// 停止录音并对录制的音频进行重采样 + 编码 + 上传
async function stopAndProcessRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
    if (stream) {
        // 关闭所有音轨
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    if (audioContext) {
        await audioContext.close();
        audioContext = null;
    }

    isRecording = false;
    resetButtonUI();

    if (audioChunks.length === 0) {
        updateStatus('⚠️ 没有录制到任何音频，请重试', true);
        audioChunks = [];
        return;
    }

    updateStatus('🎛️ 正在处理音频 ...', false, true);

    try {
        // 将录制的 Blob 读取为 ArrayBuffer
        const recordedBlob = new Blob(audioChunks, { type: 'audio/webm' }); // 默认浏览器录制格式
        const arrayBuffer = await recordedBlob.arrayBuffer();

        // 初始化 AudioContext 用于解码
        const tempAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
        let decodedBuffer = await tempAudioCtx.decodeAudioData(arrayBuffer);

        // 重采样至 16kHz (如果是多声道，转为单声道)
        let sourceBuffer = decodedBuffer;
        // 如果需要混缩为单声道 (强制单声道，避免多声道文件)
        if (sourceBuffer.numberOfChannels > 1) {
            // 创建单声道 buffer: 离线混缩
            const offlineCtx = new OfflineAudioContext(1, sourceBuffer.length, sourceBuffer.sampleRate);
            const source = offlineCtx.createBufferSource();
            source.buffer = sourceBuffer;
            source.connect(offlineCtx.destination);
            source.start();
            const renderedMono = await offlineCtx.startRendering();
            sourceBuffer = renderedMono;
        }

        // 重采样至目标 16000 Hz
        const resampledBuffer = await resampleAudioBuffer(sourceBuffer, TARGET_SAMPLE_RATE);
        // 转为 WAV 格式
        const wavBlob = bufferToWav(resampledBuffer);

        // 上传 WAV 文件
        await uploadAudioBlob(wavBlob);

    } catch (err) {
        console.error('音频处理失败:', err);
        updateStatus(`❌ 音频处理出错: ${err.message}`, true);
    } finally {
        audioChunks = [];
    }
}

// 开始录音函数
async function startRecording() {
    try {
        // 请求麦克风权限
        const constraints = {
            audio: {
                channelCount: 1,
                sampleRate: TARGET_SAMPLE_RATE,
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        };

        stream = await navigator.mediaDevices.getUserMedia(constraints);

        // 获取真实音频轨道设置
        const audioTrack = stream.getAudioTracks()[0];
        const settings = audioTrack.getSettings();
        console.log('实际音频设置:', settings);

        // 如果浏览器不支持指定采样率，我们仍然录制，后续通过重采样保证 16k
        // 创建 MediaRecorder，使用默认编码 (通常 webm)
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = async () => {
            // 停止录制后进行处理及上传
            await stopAndProcessRecording();
        };

        mediaRecorder.onerror = (err) => {
            console.error('MediaRecorder 错误:', err);
            updateStatus('录音器出错，请重试', true);
            cleanupRecording();
        };

        // 开始录制
        mediaRecorder.start(100);
        isRecording = true;
        setRecordingUI();
        updateStatus('🔴 录音中... 点击红色按钮停止并上传', false);

    } catch (err) {
        console.error('获取麦克风失败:', err);
        let errorMsg = '无法访问麦克风，请检查权限';
        if (err.name === 'NotAllowedError') errorMsg = '❌ 麦克风权限被拒绝，请允许后重试';
        else if (err.name === 'NotFoundError') errorMsg = '未检测到麦克风设备';
        updateStatus(errorMsg, true);
        cleanupRecording();
    }
}

// 清理录音资源 (不完全停止轨道的情况)
function cleanupRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    if (audioContext) {
        audioContext.close().catch(e => console.warn);
        audioContext = null;
    }
    isRecording = false;
    resetButtonUI();
    audioChunks = [];
}

function onRecordButtonClick() {
    if (isRecording) {
        // 正在录音中，停止录音并上传
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            updateStatus('⏹️ 正在停止录音并处理音频...', false);
            mediaRecorder.stop();
        } else {
            // 异常情况做清理
            cleanupRecording();
            updateStatus('录音已停止', false);
        }
    } else {
        // 未录音，开始录音
        startRecording();
    }
}

// 页面关闭时释放资源
window.addEventListener('beforeunload', () => {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
});

if (recordBtn) {
    recordBtn.addEventListener('click', onRecordButtonClick);
} else {
    console.error('事件绑定失败');
}