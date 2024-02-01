const getParams = {
    method: "GET"
};

window.addEventListener("load", pageLoad);
const interval = setInterval(getData, 5000);

async function pageLoad() {
    document.getElementById("postButton").addEventListener("click", postData);
    //document.getElementById("getButton").addEventListener("click", getData);
    await getData()
}

async function getData() {
    const response = await fetch ("/data.json", getParams);
    const data = await response.json();

    console.log(data);
    document.getElementById("temperature").innerHTML = "Temperature: " + (data['temperature'] ?? 0) + "&deg;C";
    document.getElementById("humidity").innerHTML = "Humidity: " + (data['humidity'] ?? 0) + "%";
    document.getElementById("soil_humidity").innerHTML = "Soil Humidity: " + (data['soil_humidity'] ?? 0) + "%";
}

async function postData() {
    const light = document.getElementById("light_check").checked

    const data = {
        light: light
    };

    const postParams = {
        headers: {
            "content-type": "application/json; charset=UTF-8"
        },
        body: JSON.stringify(data),
        method: "POST"
    };

    const response = await fetch ("#", postParams);
    //const data = await response.json();

    console.log(response);
}