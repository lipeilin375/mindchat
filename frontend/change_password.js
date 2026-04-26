var loader;
var CHANGE_PASSWORD_URL = `${base_url}/api/user/changepassword`;
var token = localStorage.getItem('mindchat_token');

document.addEventListener('DOMContentLoaded', function () {
    if (!token) {
        window.parent.location.href = './login.html';
        return;
    }
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
    $('button:submit').html('修改中...').attr('disabled', true);
    loader = $('button:submit').lyearloading({
        opacity: 0.2,
        spinnerSize: 'nm'
    });
}).ajaxStop(function () {
    if (loader) {
        loader.destroy();
    }
    $('button:submit').html('修改密码').attr('disabled', false);
});

$('.site-form').on('submit', function (event) {
    event.preventDefault();

    if (this.checkValidity() === false) {
        event.stopPropagation();
        $(this).addClass('was-validated');
        return false;
    }

    if (document.querySelector("#new-password").value != document.querySelector("#confirm-password").value) {
        showPageNotify('warning', '新密码和确认密码不匹配', 'animate__animated animate__shakeX');
        return false;
    }

    else {
        var payload = {
            "old_password": document.querySelector("#old-password").value,
            "new_password": document.querySelector("#new-password").value
        };

        var ajaxOptions = {
            url: CHANGE_PASSWORD_URL,
            method: 'POST',
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
                showPageNotify('success', '密码修改成功', 'animate__animated animate__fadeInUp');
                return;
            }
        }).fail(function (xhr) {
            var msg = (xhr.responseJSON && xhr.responseJSON.detail) ? xhr.responseJSON.detail : '密码修改失败，请稍后重试';
            showPageNotify('danger', msg, 'animate__animated animate__shakeX');
        });

        return false;
    }
});