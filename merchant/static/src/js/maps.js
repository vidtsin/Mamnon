
$(document).ready(function() {
  var map = null;
  var myMarker;
  var myLatlng;

  function initializeGMap(lat, lng) {
    myLatlng = new google.maps.LatLng(lat, lng);
  
    var myOptions = {
      zoom: 10,
      zoomControl: true,
      center: myLatlng,
      mapTypeId: google.maps.MapTypeId.ROADMAP,
    };

    map = new google.maps.Map(document.getElementById("map_canvas"), myOptions);
    myMarker = new google.maps.Marker({
      position: myLatlng,
      draggable: true,
    });

    myMarker.setMap(map);
    map.setZoom(10);
    
   google.maps.event.addListener(myMarker, 'dragend', function(marker){
      var latLng = myMarker.position;
      currentLatitude = latLng.lat();
      currentLongitude = latLng.lng();
      var geocoder = new google.maps.Geocoder;
      var latLng = new google.maps.LatLng(currentLatitude, currentLongitude);
      geocoder.geocode({'location': latLng}, function (results, status) {
          if (status === 'OK') {
              $('#autocomplete').val(results[0].formatted_address);
              var filtered_array = results[0].address_components.filter(function(address_component){
                    return address_component.types.includes("country");
                });
              var country = filtered_array.length ? filtered_array[0].short_name: "";
              $('#country').val(country);

              var filtered_array_city = results[0].address_components.filter(function(address_component){
                  return address_component.types.includes("locality");
              });            
              var city = filtered_array_city.length ? filtered_array_city[0].short_name: "";
              var city_lower = city.toLowerCase();            
              $('#city').find('option').each(function(){
                if($(this).text().toLowerCase().trim() == city_lower){
                  $('#city').val($(this).val()); 
                }
              })
          }
      });
      $("#lat").val(currentLatitude);
      $("#lng").val(currentLongitude);
   }); 
  }

function set_current_location(){
  navigator.geolocation.getCurrentPosition(function(response) {
    initializeGMap(response.coords.latitude, response.coords.longitude)
    Latlng = new google.maps.LatLng(response.coords.latitude, response.coords.longitude);
      var geocoder = new google.maps.Geocoder;    
    geocoder.geocode({'location': Latlng}, function (results, status) {
        if (status === 'OK') {
            $('#autocomplete').val(results[0].formatted_address);
            var filtered_array = results[0].address_components.filter(function(address_component){
                    return address_component.types.includes("country");
                });
            var country = filtered_array.length ? filtered_array[0].short_name: "";
            $('#country').val(country);

            var filtered_array_city = results[0].address_components.filter(function(address_component){
                return address_component.types.includes("locality");
            });            
            var city = filtered_array_city.length ? filtered_array_city[0].short_name: "";
            var city_lower = city.toLowerCase();            
            $('#city').find('option').each(function(){
              if($(this).text().toLowerCase().trim() == city_lower){
                $('#city').val($(this).val()); 
              }
            })
        }
    });
  })
}

$(document).on('click','#set_curr_location', function(e){
  e.preventDefault();
  set_current_location()
})

  // Re-init map before show modal
  $('#myModal').on('show.bs.modal', function(event) {
    var button = $(event.relatedTarget);
    var lat = button.data('lat');
    var lng = button.data('lng');
    var geolocation;
    if ((lat == '') || (lat == undefined) || (lng == '') || (lng == undefined)){
      set_current_location();
    }
    else{
      initializeGMap(lat,lng);      
    }
    $("#location-map").css("width", "100%");
    $("#map_canvas").css("width", "100%");
  });

  // Trigger map resize event after modal shown
  $('#myModal').on('shown.bs.modal', function() {
    google.maps.event.trigger(map, "resize");
    // map.setCenter(myLatlng);
  });



});