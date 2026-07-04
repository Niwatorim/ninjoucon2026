let socket = null;
function connectWebSocket(){
    socket = new WebSocket("ws://localhost:8765");
    socket.onopen=()=> console.log("Opened websocket");
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("Background recieved: ",data.action);

        chrome.tabs.query(
            {url:"https://www.youtube.com/*"},
            function(tabs){
                tabs.forEach(tab => {
                    chrome.tabs.sendMessage(tab.id,data)
                });
            })
    };

    socket.onclose = () =>{
        console.log("Closed Websocket")
        setTimeout(connectWebSocket,3000);
    };

    socket.onerror = (error) => {
        console.error("WEBSOCKET ERROR: ",error);
    }

}
connectWebSocket();