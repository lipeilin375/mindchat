var loader;
var USER_INFO_API_URL = `${base_url}/api/user/profile`;
var token = localStorage.getItem('mindchat_token');

document.addEventListener('DOMContentLoaded', function () {
    if (!token) {
        window.parent.location.href = './login.html';
        return;
    }
    $.ajax({
        url: USER_INFO_API_URL,
        method: 'GET',
        timeout: 0,
        headers: {
            'Authorization': 'Bearer ' + token
        }
    }).done(function (response, textStatus, xhr) {
        if (xhr.status === 200) {
            $('#username').val(response.username);
            $('#sex').val(response.gender);
            $('#age').val(response.age);
            $('#phone').val(response.phone);
            $('#role').val(response.role);
            if (response.is_active) {
                $('#account-status-active').show();
            } else {
                $('#account-status-inactive').show();
            }
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
});

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

$(document).ajaxStart(function () {
    $('button:submit').html('保存中...').attr('disabled', true);
    loader = $('button:submit').lyearloading({
        opacity: 0.2,
        spinnerSize: 'nm'
    });
}).ajaxStop(function () {
    if (loader) {
        loader.destroy();
    }
    $('button:submit').html('保存').attr('disabled', false);
});

$('.site-form').on('submit', function (event) {
    event.preventDefault();

    if (this.checkValidity() === false) {
        event.stopPropagation();
        $(this).addClass('was-validated');
        return false;
    }

    var payload = {
        age: parseInt($('#age').val()),
        phone: $('#phone').val()
    };

    var ajaxOptions = {
        url: USER_INFO_API_URL,
        method: 'PUT',
        timeout: 0,
        headers: {
            'Authorization': 'Bearer ' + token
        },
        contentType: 'application/json',
        processData: false,
        data: JSON.stringify(payload)
    };

    $.ajax(ajaxOptions).done(function (response, textStatus, xhr) {
        if (xhr.status === 200) {
            showPageNotify('success', '信息更新成功', 'animate__animated animate__fadeInUp');
            return;
        }

        showPageNotify('danger', '信息更新失败，请稍后重试', 'animate__animated animate__shakeX');
    }).fail(function (xhr) {
        showPageNotify('danger', '请求失败，请检查网络或后端服务', 'animate__animated animate__shakeX');
    });

    return false;
});