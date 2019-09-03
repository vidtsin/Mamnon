var placeSearch, autocomplete;
var componentForm = {
  autocomplete: 'autocomplete',
  lat:'lat', 
  lng: 'lng',
  country:'country'
};
var IsplaceChange = false;

function initAutocomplete() {
// Create the autocomplete object, restricting the search to geographical
// location types.
autocomplete = new google.maps.places.Autocomplete(
    /** @type {!HTMLInputElement} */(document.getElementById('autocomplete')),
    {types: ['geocode']});
// When the user selects an address from the dropdown, populate the address
// fields in the form.
autocomplete.addListener('place_changed', fillInAddress);
}

function fillInAddress() {
// Get the place details from the autocomplete object.
    var place = autocomplete.getPlace();

    for (var component in componentForm) {
      document.getElementById(component).val = '';
    }

    var filtered_array = place.address_components.filter(function(address_component){
        return address_component.types.includes("country");
    });
    var filtered_array_city = place.address_components.filter(function(address_component){
        return address_component.types.includes("locality");
    });

    var country = filtered_array.length ? filtered_array[0].short_name: "";
    var city = filtered_array_city.length ? filtered_array_city[0].short_name: "";
    var lat = place.geometry.location.lat();
    var lng = place.geometry.location.lng();

    city_lower = city.toLowerCase();

    $('#city').find('option').each(function(){
      if($(this).text().toLowerCase().trim() == city_lower){
        $('#city').val($(this).val()); 
      }
    })
    
    $('#country').val(country);
    $('#lat').val(lat);
    $('#lng').val(lng);
    $('#location-btn').data('lat',lat);
    $('#location-btn').data('lng',lng);

    if ($('#autocomplete').attr('redirect') == 'true'){
        change_location(country);
    }
}

function geolocate() {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(function(position) {
        var geolocation = {
          lat: position.coords.latitude,
          lng: position.coords.longitude
        };
        var circle = new google.maps.Circle({
          center: geolocation,
          radius: position.coords.accuracy
        });
        autocomplete.setBounds(circle.getBounds());
      });
    }
}

