var captcha_checked = false;
function recaptchaCallback() {
    captcha_checked = true;
};

$(document).on('submit', '#login-form', function(e){
    e.preventDefault();
   
    $('#otp-error-msg').remove();
    if (captcha_checked == false){
        $('.login_form').prepend('<div id="otp-error-msg" class="alert alert-danger"><span>Invalid reCAPTCHA</span></div>');
        return false;
    }
    $('#loader').removeClass('hidden');
    if ((grecaptcha.getResponse() == '') || (grecaptcha.getResponse() == undefined)){
        $('.login_form').prepend('<div id="otp-error-msg" class="alert alert-danger"><span>Invalid reCAPTCHA</span></div>');
        return;
    }
    var username = $('input[name="username"]').val();
    var password = $('input[name="password"]').val();
    $.ajax({
        url: '/accounts/check_authenticate/',
        data: {
            'username': username,
            'password': password,
        },
        dataType: 'json',
        success: function (result) {
            if (result.error){
                $('#loader').addClass('hidden');
                $('.login_form').prepend('<div id="otp-error-msg" class="alert alert-danger"><span>'+result.error_msg+'</span></div>');
                $('.login_form').find('input').each(function(){
                    $(this).addClass('otp-error');
        		});
        		// return false;
        	}
        	else{
        		if (result.need_auth){
              $('#loader').addClass('hidden');
                    $("#otp-error-msg").remove();
                    $('.otp-input').removeClass('otp-input-error');
                    $('.otp-input').val('');
                    $('#otpModal').modal('show');
				}
				else{
					ajax_login();
				}
        	}
        },
        error:function(error){
            $('#loader').addClass('hidden');
            $('.login_form').prepend('<div id="otp-error-msg" class="alert alert-danger"><span>Error logging in! Try later.</span></div>');
        }
  	});
  	return;
});