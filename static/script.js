window.addEventListener("load", pageLoad);

async function pageLoad() {
    document.getElementById("postButton").addEventListener("click", postData);
    //document.getElementById("getButton").addEventListener("click", getData);
    await getData()
    setInterval(getData, 5000);
}

async function getData() {
    const getParams = {
        method: "GET"
    };

    const response = await fetch ("/data.json", getParams);
    const data = await response.json();

    document.getElementById("co2").innerHTML = "CO2: " + (data['co2'] ?? 0) + "ppm";
    document.getElementById("temperature").innerHTML = "Temperature: " + (data['temperature'] ?? 0).toFixed(2) + "&deg;C";
    document.getElementById("humidity").innerHTML = "Humidity: " + (data['humidity'] ?? 0).toFixed(2) + "%";
    document.getElementById("soil_humidity").innerHTML = "Soil Humidity: " + (data['soil_humidity'] ?? 0);
}

async function postData() {
    const light = document.getElementById("light_check").checked
    const water = document.getElementById("water_check").checked

    const data = {
        light: light,
        water: water
    };

    const postParams = {
        headers: {
            "content-type": "application/json; charset=UTF-8"
        },
        body: JSON.stringify(data),
        method: "POST"
    };

    await fetch ("#", postParams);
}