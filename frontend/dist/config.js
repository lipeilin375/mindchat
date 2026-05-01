// const base_url = "http://127.0.0.1:8000"
const base_url = "https://api.mindchat.dpdns.org"

function clearTempStorage() {
    localStorage.removeItem('mindchat_token');
    localStorage.removeItem('mindchat_user');
    sessionStorage.clear();
}

$(document).ready(function (e) {
    if (!localStorage.getItem('mindchat_user') || JSON.parse(localStorage.getItem('mindchat_user')).role != 'admin') {
        window.location.href = './login.html';
    }
    while (1) {
        setTimeout(() => {
            var token = localStorage.getItem('mindchat_token');
            $.ajax({
                url: base_url + '/api/auth/me',
                method: 'GET',
                timeout: 0,
                headers: {
                    'Authorization': 'Bearer ' + token
                }
            }).done(function (response, textStatus, xhr) {
                if (xhr.status === 401) {
                    showPageNotify('warning', '登录状态已过期，请重新登录', 'animate__animated animate__shakeX');
                    clearTempStorage();
                    setTimeout(function () {
                        window.parent.location.href = './login.html';
                    }, 1200);
                }
            }).fail(function (xhr) {
                showPageNotify('danger', '请求失败，请检查网络或后端服务', 'animate__animated animate__shakeX');
                clearTempStorage();
                setTimeout(function () {
                    window.parent.location.href = './login.html';
                }, 1200);
            });
        }, 1000 * 60 * 10);
    }
});