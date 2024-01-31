const data = {
    temperature: 69,
    humidity: 420,
    atm_pressure: 42069
};

const params = {
    headers: {
        "content-type": "application/json; charset=UTF-8"
    },
    body: JSON.stringify(data),
    method: "POST"
};

const params2 = {
    method: "GET"
};

document.getElementById("postButton").addEventListener("click", () => {
    fetch ("#", params)
    .then(res => console.log(res))
    .catch(error => console.log(error))
});
document.getElementById("getButton").addEventListener("click", getData);

async function getData() {
    const response = await fetch ("/data.json", params2);
    const data = await response.json();

    console.log(data);
    document.getElementById("temperature").innerHTML = "Temperature: " + data['temperature'];
    document.getElementById("humidity").innerHTML = "Humidity: " + data['humidity'];
    document.getElementById("atm_pressure").innerHTML = "Atmospheric Pressure: " + data['atm_pressure'];
}