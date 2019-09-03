$(document).on('change', '.fileHidden', function(e){
  var file_size = $(this)[0].files[0].size / 1000;
  var validator = $('#merchant-form').validate();
  if (file_size > parseFloat(max_file_upload_size)){
    bootbox.alert('Image size too large.');    
    setTimeout(function(){$(this).val('');
    $(this).parent().parent().find('img').attr('src','');}, 500);
    return false;
  }
});

$('#merchant-form').validate({
     errorPlacement: function(error, element) {
       if (element.attr("name") == "terms") {    
           error.insertBefore( $("#terms") );

       } else {
           error.insertAfter(element);
       }
     },
    rules: {
        terms: {
            required : true
        },
    },
    messages:{
        terms: {
            required : "Please agree terms & conditions."
        }
    }
})

// Change the button text & add active class
$('.jRadioDropdown').change(function() {
  var dropdown = $(this).closest('.dropdown');
  var thislabel = $(this).closest('label');

  dropdown.find('label').removeClass('active');
  if( $(this).is(':checked') ) {
    thislabel.addClass('active');
    dropdown.find('ins').html( thislabel.text() );
  }

});    
 

//Add tabindex on labels
$('label.dropdown-item').each(function (index, value){
	$(this).attr('tabindex', 0 );
	$(this).find('input').attr('tabindex', -1 );
});

//Add keyboard navigation
$('label.dropdown-item').keypress(function(e){
  if((e.keyCode ? e.keyCode : e.which) == 13){
    $(this).find('input').trigger('click');
    $(this).closest('.dropdown').dropdown('toggle')
  }
});

function readURL(input) {
    if (input.files && input.files[0]) {
        var reader = new FileReader();
        
        reader.onload = function (e) {
            $('#logo-preview').attr('src', e.target.result);
        }
        
        reader.readAsDataURL(input.files[0]);
    }
}

$("#logo").change(function(){
    readURL(this);
});
