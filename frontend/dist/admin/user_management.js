const USER_API = `${base_url}/api/admin/users`;
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
    elem: '#userTable',
    url: USER_API,
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

      { field: 'username', title: '用户名' },

      {
        field: 'gender',
        title: '性别',
        width: 80,
        templet: d => d.gender === '女'
          ? '<span class="layui-badge layui-bg-pink">女</span>'
          : '<span class="layui-badge layui-bg-blue">男</span>'
      },

      { field: 'age', title: '年龄', width: 80 },

      { field: 'phone', title: '手机号', width: 150 },

      {
        field: 'is_active',
        title: '状态',
        width: 100,
        templet: d => d.is_active
          ? '<span class="layui-badge layui-bg-green">正常</span>'
          : '<span class="layui-badge">禁用</span>'
      },

      {
        field: 'created_at',
        title: '创建时间',
        templet: d => formatToChinaTime(d.created_at)
      },

      { fixed: 'right', title: '操作', toolbar: '#toolbarTpl', width: 150 }
    ]]
  });

  document.getElementById('searchBtn').onclick = function () {
    const keyword = document.getElementById('searchInput').value;

    table.reload('userTable', {
      where: {
        search: keyword
      },
      page: {
        curr: 1
      }
    });
  };

  table.on('tool(userTableFilter)', function (obj) {
    const data = obj.data;

    if (obj.event === 'detail') {
      showDetailModal(data);
      // 打开 Bootstrap modal
      const modal = new bootstrap.Modal(document.getElementById('detailModal'));
      modal.show();
    }

    if (obj.event === 'toggle') {

      const newStatus = !data.is_active;

      layer.confirm(
        `确定要${newStatus ? '启用' : '禁用'}用户 ${data.username} 吗？`,
        function (index) {
          fetch(`${base_url}/api/admin/users/${data.id}/status`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({
              is_active: newStatus
            })
          })
            .then(res => {
              if (!res.ok) throw new Error();
              return res.json();
            })
            .then(() => {
              layer.msg('操作成功');
              obj.update({
                is_active: newStatus
              });

              table.reload('userTable', {
                where: tableIns.config.where,
                page: {
                  curr: $(".layui-laypage-em").next().html() || 1
                }
              });

            })
            .catch(() => {
              layer.msg('操作失败');
            });
          layer.close(index);
        }
      );
    }
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
  const USER_DETAIL_API = `${base_url}/api/admin/users/${data.id}`;
  const USER_ANALYZE_API = `${base_url}/api/admin/users/${data.id}/analyses`

  $.ajax({
    url: USER_DETAIL_API,
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
      window.parent.location.href = '../login.html';
    }, 1200);
  });

  layui.use(['table'], function () {
    const table = layui.table;

    // 渲染表格
    const tableIns = table.render({
      elem: '#userHistoryTable',
      url: USER_ANALYZE_API,
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
              case 'disgust': primary_emotion_badge = '<span class="layui-badge layui-bg-red">厌恶</span>'; break;
              case 'fear': primary_emotion_badge = '<span class="layui-badge layui-bg-dark">恐惧</span>'; break;
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
              case 'severe': depression_level_badge = '<span class="layui-badge layui-bg-red">严重</span>'; break;
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

        { fixed: 'right', title: '操作', toolbar: '#toolbarHistoryTpl', width: 120 }
      ]],
      done: function () {
        // 让进度条生效
        layui.element.render('progress');
      }
    });

    // 监听工具栏事件
    table.on('tool(userHistoryTableFilter)', function (obj) {
      const d = obj.data;
      if (obj.event === 'detail') {
        showEmotionModal(data.id, d.analysis_id);

        // 打开 Bootstrap modal
        const modal = new bootstrap.Modal(document.getElementById('emotionModal'));
        modal.show();
      }
    });

    table.on('page(userHistoryTableFilter)', function (obj) {
      const page = obj.curr;
      const limit = obj.limit;

      table.reload('userHistoryTable', {
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

function showEmotionModal(user_id, analysis_id) {
  const url = `${base_url}/api/admin/users/${user_id}/analyses/${analysis_id}`;
  var mTitle = document.querySelector("#emotionModalLabel")
  var mPrimaryEmotion = document.querySelector("#emotion_primary_emotion")
  var mDepressionLevel = document.querySelector("#emotion_depression_level")
  var mPhqScore = document.querySelector("#emotion_phq_score")
  var mCreatedAt = document.querySelector("#emotion_created_at")
  var mASRText = document.querySelector("#emotion_ASR_text")
  var mAnalysisResult = document.querySelector("#emotion_analysis_result")
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
      mTitle.innerText = `分析详情`;
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
      window.parent.location.href = '../login.html';
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