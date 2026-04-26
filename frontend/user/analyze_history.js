var loader;
var HISTORY_API_URL = `${base_url}/api/analysis/history`;
var token = localStorage.getItem('mindchat_token');
let modalChart = null;

$(document).ajaxStart(function () {
  loader = $('body').lyearloading({
    opacity: 0.2,
    spinnerSize: 'nm'
  });
}).ajaxStop(function () {
  if (loader) {
    loader.destroy();
  }
});

let code = ``;

window.onload = function () {
  loader = document.getElementById('loader');
  layui.use(['table'], function () {
    const table = layui.table;

    // 渲染表格
    const tableIns = table.render({
      elem: '#historyTable',
      url: HISTORY_API_URL,
      method: 'GET',
      headers: {
        'Authorization': 'Bearer ' + token
      },

      page: true,
      limit: 10,
      limits: [5, 10, 20, 50],

      request: {
        pageName: 'page',
        limitName: 'limit'
      },
      where: {
      },
      before: function (obj) {
        const page = obj.page?.curr || 1;
        const limit = obj.page?.limit || 10;

        obj.where.skip = (page - 1) * limit;
        obj.where.limit = limit;

        delete obj.where.page;
      },
      parseData: function (res) {
        return {
          code: 0,
          msg: '',
          count: res.total,
          data: res.items
        };
      },
      cols: [[
        {
          field: 'primary_emotion',
          title: '主要情绪',
          templet: function (d) {
            let primary_emotion_badge = '';
            switch (d.primary_emotion) {
              case 'joy': primary_emotion_badge = '<span class="layui-badge layui-bg-green">开心</span>'; break;
              case 'sadness': primary_emotion_badge = '<span class="layui-badge layui-bg-blue">难过</span>'; break;
              case 'anger': primary_emotion_badge = '<span class="layui-badge layui-bg-orange">生气</span>'; break;
              case 'neutral': primary_emotion_badge = '<span class="layui-badge layui-bg-gray">中性</span>'; break;
              case 'disgust': primary_emotion_badge = '<span class="layui-badge">厌恶</span>'; break;
              case 'fear': primary_emotion_badge = '<span class="layui-badge layui-bg-black">恐惧</span>'; break;
              default: primary_emotion_badge = '<span class="layui-badge layui-bg-gray">未知</span>';
            }
            return primary_emotion_badge;
          }
        },

        {
          field: 'depression_level',
          title: '抑郁等级',
          templet: function (d) {
            let depression_level_badge = '';
            switch (d.depression_level) {
              case 'none': depression_level_badge = '<span class="layui-badge layui-bg-green">无</span>'; break;
              case 'mild': depression_level_badge = '<span class="layui-badge layui-bg-blue">轻微</span>'; break;
              case 'moderate': depression_level_badge = '<span class="layui-badge layui-bg-orange">中等</span>'; break;
              case 'severe': depression_level_badge = '<span class="layui-badge">严重</span>'; break;
              default: depression_level_badge = '<span class="layui-badge layui-bg-gray">未知</span>';
            }
            return depression_level_badge;
          }
        },

        {
          field: 'phq_score',
          title: 'PHQ指数',
          templet: function (d) {
            let phq_progress = '';
            if (d.phq_score >= 15) {
              phq_progress = '<div class="layui-progress"><div class="layui-progress-bar layui-bg-red" style="width:100%"></div></div>';
            } else if (d.phq_score >= 10) {
              phq_progress = '<div class="layui-progress"><div class="layui-progress-bar layui-bg-orange" style="width:75%"></div></div>';
            } else if (d.phq_score >= 5) {
              phq_progress = '<div class="layui-progress"><div class="layui-progress-bar layui-bg-blue" style="width:50%"></div></div>';
            } else {
              phq_progress = '<div class="layui-progress"><div class="layui-progress-bar layui-bg-green" style="width:25%"></div></div>';
            }
            return phq_progress;
          }
        },

        {
          field: 'created_at', title: '上传时间',
          templet: function (d) {
            return formatToChinaTime(d.created_at);
          }
        },

        { fixed: 'right', title: '操作', toolbar: '#toolbarTpl', width: 120 }
      ]],
      done: function () {
        // 让进度条生效
        layui.element.render('progress');
      }
    });

    // 监听工具栏事件
    table.on('tool(historyTableFilter)', function (obj) {
      const data = obj.data;
      if (obj.event === 'detail') {
        showDetailModal(data.analysis_id, data.index - 1);

        // 打开 Bootstrap modal
        const modal = new bootstrap.Modal(document.getElementById('detailModal'));
        modal.show();
      }
    });

    table.on('page(historyTableFilter)', function (obj) {
      const page = obj.curr;
      const limit = obj.limit;

      table.reload('historyTable', {
        where: {
          skip: (page - 1) * limit,
          limit: limit
        },
        page: {
          curr: page
        }
      });
    });

  });
}

function showDetailModal(analysis_id, index) {
  const url = `${base_url}/api/analysis/${analysis_id}`;
  var mTitle = document.querySelector("#detailModalLabel")
  var mPrimaryEmotion = document.querySelector("#detail_primary_emotion")
  var mDepressionLevel = document.querySelector("#detail_depression_level")
  var mPhqScore = document.querySelector("#detail_phq_score")
  var mCreatedAt = document.querySelector("#detail_created_at")
  var mASRText = document.querySelector("#detail_ASR_text")
  var mAnalysisResult = document.querySelector("#detail_analysis_result")
  var mSuggestion = document.querySelector("#accordionSuggestion")
  var emotionChartContainer = document.querySelector("#emotion_distribution_chart")
  $.ajax({
    url: url,
    method: 'GET',
    timeout: 0,
    headers: {
      'Authorization': 'Bearer ' + token
    }
  }).done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      mTitle.innerText = `分析详情 - ID: ${index + 1}`;
      let primaryEmotionText = "未知";
      switch (response.primary_emotion) {
        case 'joy':
          primaryEmotionText = "开心";
          break;
        case 'sadness':
          primaryEmotionText = "难过";
          break;
        case 'anger':
          primaryEmotionText = "生气";
          break;
        case 'neutral':
          primaryEmotionText = "中性";
          break;
        case 'disgust':
          primaryEmotionText = "厌恶";
          break;
        case 'fear':
          primaryEmotionText = "恐惧";
          break;
        default:
          primaryEmotionText = "未知";
      }
      mPrimaryEmotion.innerText = primaryEmotionText;
      let primaryEmotionRGB = "bg-secondary"; // 默认灰色
      switch (response.primary_emotion) {
        case 'joy':
          primaryEmotionRGB = "bg-success";
          break;
        case 'sadness':
          primaryEmotionRGB = "bg-info";
          break;
        case 'anger':
          primaryEmotionRGB = "bg-warning";
          break;
        case 'neutral':
          primaryEmotionRGB = "bg-secondary";
          break;
        case 'disgust':
          primaryEmotionRGB = "bg-danger";
          break;
        case 'fear':
          primaryEmotionRGB = "bg-dark";
          break;
        default:
          primaryEmotionRGB = "bg-secondary";
      }
      mPrimaryEmotion.className += " " + primaryEmotionRGB;
      let depressionLevelText = "未知";
      switch (response.depression_level) {
        case 'none':
          depressionLevelText = "无";
          break;
        case 'mild':
          depressionLevelText = "轻微";
          break;
        case 'moderate':
          depressionLevelText = "中等";
          break;
        case 'severe':
          depressionLevelText = "严重";
          break;
        default:
          depressionLevelText = "未知";
      }
      mDepressionLevel.innerText = depressionLevelText;
      mPhqScore.innerText = response.phq_score !== undefined ? response.phq_score : "未知";
      mCreatedAt.innerText = formatToChinaTime(response.created_at) || "未知";
      mASRText.innerText = response.transcription || "无转录文本";
      mAnalysisResult.innerText = response.llm_analysis || "无分析结果";
      show_emotion_suggestion(response.suggestions, mSuggestion);
      show_emotion_chart(response.emotion_scores, emotionChartContainer);
    } else {
      showPageNotify('danger', response.detail, 'animate__animated animate__shakeX');
    }
  }).fail(function (xhr) {
    showPageNotify('danger', '请求失败，请检查网络或后端服务', 'animate__animated animate__shakeX');
    clearTempStorage();
    setTimeout(function () {
      window.parent.location.href = './login.html';
    }, 1200);
  });
}

function formatToChinaTime(str) {
  if (!str) return "";

  // 如果字符串没有时区信息（没有Z或±hh:mm），默认当作UTC处理
  const hasTimezone = /[Zz]|[+-]\d{2}:\d{2}$/.test(str);
  const safeStr = hasTimezone ? str : str + "Z";

  const date = new Date(safeStr);

  if (isNaN(date.getTime())) {
    return "Invalid Date";
  }

  return date.toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai", // 或 Asia/Singapore
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });
}

function show_emotion_chart(emotion_scores, container) {
  if (modalChart) {
    modalChart.destroy();
  }
  const labelsCN = ["开心", "难过", "生气", "中性", "厌恶", "恐惧"];
  const emotionKeys = ["joy", "sadness", "anger", "neutral", "disgust", "fear"];
  const dataValues = emotionKeys.map(key => emotion_scores[key] || 0);
  modalChart = new Chart(container, {
    type: 'pie',
    data: {
      labels: labelsCN,
      datasets: [
        {
          label: '情绪分析概率分布',
          data: dataValues,
          backgroundColor: [
            "#4CAF50",
            "#2196F3",
            "#FF9800",
            "#9E9E9E",
            "#F44336",
            "#000000"
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
          text: '情绪分析概率分布'
        }
      }
    },
  });
}

function show_emotion_suggestion(suggestions, container) {
  container.innerHTML = "";
  if (!suggestions || !Array.isArray(suggestions)) {
    return;
  }
  suggestions.forEach(function (suggestion, index) {
    var accordionItem = document.createElement("div");
    accordionItem.className = "accordion-item";
    accordionItem.innerHTML = `
            <h2 class="accordion-header" id="heading${index}">
                <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapse${index}" aria-expanded="true" aria-controls="collapse${index}">
                    建议 - #${index + 1}
                </button>
            </h2>
            <div id="collapse${index}" class="accordion-collapse collapse" aria-labelledby="heading${index}" data-bs-parent="#accordionSuggestion">
                <div class="accordion-body">
                    ${suggestion}
                </div>
            </div>
        `;
    container.appendChild(accordionItem);
  });
}