function ApparentTemperature(dry_bulb_temperature, relative_humidity, wind_speed){

  // Make a POST request with a JSON payload.
  var data = {
    'dry_bulb_temperature': dry_bulb_temperature,
    'relative_humidity': relative_humidity,
    'wind_speed': wind_speed
  };
  
  var options = {
    'method' : 'post',
    'contentType': 'application/json',
    // Convert the JavaScript object to a JSON string.
    'payload' : JSON.stringify(data)
  };
  
  var response = UrlFetchApp.fetch('https://australia-southeast1-bus5001-361804.cloudfunctions.net/calculate-feels-like-temperature', options);

  return JSON.parse(response.getContentText())

}