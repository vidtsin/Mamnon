$(document).ready(function(){
	$.ajax({
		url: '/loyalty/check_merchant_txns',
		method:"POST",
		dataType:"json",
		success: function(result) {
		if (result.show_tx_notification_popup == true){
				$("#notify-msgs").html(result.notify_msg);
				$('#merchant-notify-modal').modal('show');
			}
		},			
	});
	
	$(document).on('click', '#rem-ltr-btn', function(){
		$('#merchant-notify-modal').modal('hide');
	});

});

$(document).on('click','#send_otp', function(e){
    $('#send_otp').attr("disabled", true);
    setTimeout(function() { 
		$('#send_otp').removeAttr("disabled");
    }, 30000);// delay for 30 secs.			
})	