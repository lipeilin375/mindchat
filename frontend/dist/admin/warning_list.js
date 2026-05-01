const ALERT_LIST_API = `${base_url}/api/admin/alerts`;
const token = localStorage.getItem('mindchat_token');
let modalChart = null;
var loader;

window.onload = function () {
  loader = document.getElementById('loader');
}

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

layui.use(['table'], function () {
  const table = layui.table;
  const tableIns = table.render({
    elem: '#warningTable',
    url: ALERT_LIST_API,
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

    where: {},

    before: function (obj) {
      const page = obj.page?.curr || 1;
      const limit = obj.limit || 10;

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
      { field: 'id', title: 'ID', width: 80 },

      {
        field: 'level',
        title: '预警等级',
        templet: d => d.level === 'critical'
          ? '<span class="layui-badge layui-bg-red">高</span>'
          : d.level === 'warning'
            ? '<span class="layui-badge layui-bg-orange">中</span>'
            : '<span class="layui-badge layui-bg-green">低</span>'
      },

      { field: 'message', title: '预警信息', width: 200 },

      {
        field: 'is_read',
        title: '状态',
        width: 100,
        templet: d => d.is_read
          ? '<span class="layui-badge layui-bg-gray">已读</span>'
          : '<span class="layui-badge layui-bg-green">未读</span>'
      },

      {
        field: 'created_at',
        title: '创建时间',
        templet: d => formatToChinaTime(d.created_at)
      },

      { fixed: 'right', title: '操作', toolbar: '#toolbarAlertTpl', width: 150 }
    ]]
  });

  table.on('tool(warningTableFilter)', function (obj) {
    const d = obj.data;

    if (obj.event === 'detail') {
      showDetailModal(d);
      // 打开 Bootstrap modal
      const modal = new bootstrap.Modal(document.getElementById('alertModal'));
      modal.show();
    }
  });

  table.on('page(warningTableFilter)', function (obj) {
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

// 🕒 时间格式化（你之前的函数复用）
function formatToChinaTime(str) {
  if (!str) return "";

  const hasTimezone = /[Zz]|[+-]\d{2}:\d{2}$/.test(str);
  const safeStr = hasTimezone ? str : str + "Z";

  const date = new Date(safeStr);

  return date.toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });
}

function showDetailModal(data) {
  console.log(data)

  markAlertRead(data.id);

  const USER_INFO_API = `${base_url}/api/admin/users/${data.user_id}`;
  const ALERT_DETAIL_API = `${base_url}/api/admin/users/${data.user_id}/analyses/${data.analysis_id}`;
  $.ajax({
    url: USER_INFO_API,
    method: 'GET',
    timeout: 0,
    headers: {
      'Authorization': 'Bearer ' + token
    }
  }).done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      document.querySelector("#detail_user_id").innerText = response.id
      document.querySelector("#detail_username").innerText = response.username
      document.querySelector("#detail_role").innerText = response.role === 'admin' ? '管理员' : '普通用户'
      document.querySelector("#detail_status").innerText = response.is_active ? '启用' : '禁用'
      document.querySelector("#detail_status").className = response.is_active ? 'badge bg-success' : 'badge bg-danger';
      document.querySelector("#detail_gender").innerText = response.gender
      document.querySelector("#detail_age").innerText = response.age
      document.querySelector("#detail_phone").innerText = response.phone
      document.querySelector("#detail_created_at").innerText = formatToChinaTime(response.created_at)
      return;
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


  var mPrimaryEmotion = document.querySelector("#emotion_primary_emotion")
  var mDepressionLevel = document.querySelector("#emotion_depression_level")
  var mPhqScore = document.querySelector("#emotion_phq_score")
  var mCreatedAt = document.querySelector("#emotion_created_at")
  var mASRText = document.querySelector("#emotion_ASR_text")
  var mAnalysisResult = document.querySelector("#emotion_analysis_result")
  var mSuggestion = document.querySelector("#accordionSuggestion")
  var emotionChartContainer = document.querySelector("#emotion_distribution_chart")
  $.ajax({
    url: ALERT_DETAIL_API,
    method: 'GET',
    timeout: 0,
    headers: {
      'Authorization': 'Bearer ' + token
    }
  }).done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
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
          primaryEmotionRGB = "layui-bg-green";
          break;
        case 'sadness':
          primaryEmotionRGB = "layui-bg-blue";
          break;
        case 'anger':
          primaryEmotionRGB = "layui-bg-orange";
          break;
        case 'neutral':
          primaryEmotionRGB = "layui-bg-gray";
          break;
        case 'disgust':
          primaryEmotionRGB = "layui-bg-red";
          break;
        case 'fear':
          primaryEmotionRGB = "layui-bg-dark";
          break;
        default:
          primaryEmotionRGB = "layui-bg-gray";
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

function markAlertRead(alertId) {
  const READ_MARK_API = `${base_url}/api/admin/alerts/${alertId}/read`;
  $.ajax({
    url: READ_MARK_API,
    method: 'PUT',
    timeout: 0,
    headers: {
      'Authorization': 'Bearer ' + token
    }
  }).done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      userId = response.user_id;
      analysisId = response.analysis_id;
      return userId, analysisId;
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

function showPageNotify(type, message, enterAnimation) {
  $.notify({
    message: message
  }, {
    type: type,
    placement: {
      from: 'top',
      align: 'right'
    },
    z_index: 10800,
    delay: 1800,
    animate: {
      enter: enterAnimation,
      exit: 'animate__animated animate__fadeOutDown'
    }
  });
}