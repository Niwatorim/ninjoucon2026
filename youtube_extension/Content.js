/*
Await input
python ->
Seek to that valuel
*/

let stop_time_listener = null;

console.log("Content.js loaded");

let time_update_listener_attached = false;

chrome.runtime.onMessage.addListener((request,sender, sendResponse) =>{
    console.log("Content Script command: ", request.action);
    console.log("Time to turn: ", request.seek_time);

    const video = document.querySelector("video");
    const duration = video.duration;
    if (!video) return;
    
    if (!time_update_listener_attached) {
        video.addEventListener("timeupdate", () => {
            chrome.runtime.sendMessage({
                type: "TIME_UPDATE",
                currentTime: video.currentTime
            });
        });
        time_update_listener_attached = true;
    }
    if(request.action == "pause") video.pause();
    if(request.action == "seek") video.currentTime = request.seek_time;
    if(request.action == "play") video.play();
    if(request.action == "mini_seek") video.currentTime += request.seek_time;

    if(request.action == "play_until"){
        video.play();
        
        function checkTime() {
            if(video.currentTime >= request.target_time){
                video.pause();
                video.currentTime = request.target_time;
                console.log(`Reached time, pausing video at ${request.target_time}`);
                chrome.runtime.sendMessage({type: "ARRIVED"});
            }
            else {
                requestAnimationFrame(checkTime);
            }
        }
        requestAnimationFrame(checkTime);
    }
});



