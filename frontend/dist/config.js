// const base_url = "http://127.0.0.1:8000"
const base_url = "https://api.mindchat.dpdns.org"

function clearTempStorage() {
    localStorage.removeItem('mindchat_token');
    localStorage.removeItem('mindchat_user');
    sessionStorage.clear();
}


$(document).ready(async function () {
    if (location.pathname === '/login.html' || location.pathname === '/register.html') {
        clearTempStorage();
        return;
    } else if (location.pathname === '/index.html' || location.pathname === '/admin.html' || location.pathname === '/') {
        // 其他页面需要验证登录状态
        const userStr = localStorage.getItem('mindchat_user');

        if (!userStr) {
            window.location.href = './login.html';
            return;
        }

        if (JSON.parse(userStr).role !== 'admin' && location.pathname == '/admin.html') {
            window.location.href = './index.html';
            return;
        }

        if (JSON.parse(userStr).role === 'admin' && location.pathname == '/index.html') {
            window.location.href = './admin.html';
            return;
        }

        // 先验证一次
        const isValid = await authToken();
        if (!isValid) {
            clearTempStorage();
            redirectToLogin();
            return;
        }

        // 每10分钟验证一次
        setInterval(async () => {
            const valid = await authToken();
            if (!valid) {
                clearTempStorage();
                redirectToLogin();
            }
        }, 600000);

    }
});


function redirectToLogin() {
    showPageAuthNotify('warning', '登录状态已过期，请重新登录', 'animate__animated animate__shakeX');
    setTimeout(() => {
        window.location.href = './login.html';
    }, 1200);
}


async function authToken() {
    const token = localStorage.getItem('mindchat_token');

    if (!token) return false;

    try {
        const response = await $.ajax({
            url: base_url + '/api/auth/me',
            method: 'GET',
            timeout: 0,
            headers: {
                'Authorization': 'Bearer ' + token
            }
        });

        return true;
    } catch (xhr) {
        if (xhr.status === 401) {
            return false;
        }

        showPageAuthNotify('danger', '请求失败，请检查网络或后端服务', 'animate__animated animate__shakeX');
        return false;
    }
}


function showPageAuthNotify(type, message, enterAnimation) {
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