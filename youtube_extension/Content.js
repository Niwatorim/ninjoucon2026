/*
Await input
python ->
Seek to that valuel
*/

console.log("Content.js loaded");

chrome.runtime.onMessage.addListener((request,sender, sendResponse) =>{
    console.log("Content Script command: ", request.action);
    console.log("Time to turn: ", request.seek_time);

    const video = document.querySelector("video");
    const duration = video.duration;
    if (!video) return;
    if(request.action == "pause") video.pause();
    if(request.action == "seek") video.currentTime = request.seek_time*duration;
    if(request.action == "play") video.play();
    if(request.action == "mini_seek") video.currentTime += request.seek_time;

});



