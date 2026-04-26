var loader;
var ADMIN_STATS_API_URL = `${base_url}/api/analysis/history`;
var token = localStorage.getItem('mindchat_token');

document.addEventListener('DOMContentLoaded', function () {
    if (!token) {
        window.parent.location.href = './login.html';
        return;
    }
});

window.onload = function () {
    loader = document.getElementById('loader');
    $.ajax({
        url: ADMIN_STATS_API_URL,
        method: 'GET',
        timeout: 0,
        headers: {
            'Authorization': 'Bearer ' + token
        }
    }).done(function (response, textStatus, xhr) {
        if (xhr.status === 200) {
            document.querySelector("#total_analyses").innerText = response.length;
            var emotion = {
                "angry": 0,
                "disgust": 0,
                "fear": 0,
                "happy": 0,
                "neutral": 0,
                "sad": 0
            };
            var depression = { "none": 0, "mild": 0, "moderate": 0, "severe": 0 }
            var depression_count = 0
            response.forEach(e => {
                if (e.depression_level === 'severe') {
                    depression_count++;
                }
                emotion[e.primary_emotion] += 1
                depression[e.depression_level] += 1
            });
            document.querySelector("#count_alerts").innerText = depression_count;

            show_emotion_chart(emotion)
            show_depression_chart(depression);
            return;
        } else {
            showPageNotify('danger', '获取用户信息失败，请重新登录', 'animate__animated animate__shakeX');
            clearTempStorage();
            setTimeout(function () {
                location.href = './login.html';
            }, 1200);
        }
    }).fail(function (xhr) {
        showPageNotify('danger', '请求失败，请检查网络或后端服务', 'animate__animated animate__shakeX');
        clearTempStorage();
        setTimeout(function () {
            window.parent.location.href = './login.html';
        }, 1200);
    });
};

function show_depression_chart(distribution) {
    const dist = distribution || { none: 0, mild: 0, moderate: 0, severe: 0 };
    const labelsCN = ["无", "轻微", "中等", "严重"];

    new Chart($('#depression_chart'), {
        type: 'doughnut',
        data: {
            labels: labelsCN,
            datasets: [
                {
                    label: '抑郁程度分布',
                    data: [
                        dist.none || 0,
                        dist.mild || 0,
                        dist.moderate || 0,
                        dist.severe || 0
                    ],
                    backgroundColor: [
                        "#4CAF50",
                        "#FFC107",
                        "#FF9800",
                        "#F44336"
                    ]
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: '抑郁程度分布'
                }
            }
        },
    });
}

function show_emotion_chart(distribution) {
    const dist = distribution || { happy: 0, neutral: 0, disgust: 0, fear: 0, sad: 0, angry: 0 };
    const labelsCN = ["开心", "中性", "厌恶", "恐惧", "伤心", "愤怒"];

    new Chart($('#emotion_chart'), {
        type: 'polarArea',
        data: {
            labels: labelsCN,
            datasets: [
                {
                    label: '情绪分布',
                    data: [
                        dist.happy || 0,
                        dist.neutral || 0,
                        dist.disgust || 0,
                        dist.fear || 0,
                        dist.sad || 0,
                        dist.angry || 0
                    ],
                    backgroundColor: [
                        'rgba(21, 195, 119, 0.95)',
                        'rgba(108, 117, 125, 0.95)',
                        'rgba(243, 202, 78, 0.95)',
                        'rgba(0, 123, 255, 0.95)',
                        'rgba(240, 143, 17, 0.95)',
                        'rgba(244, 66, 54, 0.95)',
                    ]
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: '情绪分布'
                }
            }
        },
    });
}