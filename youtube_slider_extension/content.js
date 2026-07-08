function injectSegmentSlider() {
    if (document.getElementById('segment-overlay-container')) return;

    const playerControls = document.querySelector('.ytp-chrome-bottom');
    const videoElement = document.querySelector('video');

    if (playerControls && videoElement) {
        // If duration isn't available yet, wait for it to load
        if (isNaN(videoElement.duration) || videoElement.duration === 0) {
            videoElement.addEventListener('loadedmetadata', injectSegmentSlider, { once: true });
            return;
        }

        // Setup WebSocket connection to local Python server
        const ws = new WebSocket('ws://localhost:8000');
        ws.onopen = () => console.log('Connected to Checkpoint WebSocket Server');
        ws.onerror = (err) => console.error('Checkpoint WebSocket Error:', err);
        
        // 1. The Main Container (sits just above the YouTube progress bar)
        const container = document.createElement('div');
        container.id = 'segment-overlay-container';
        container.style.position = 'absolute';
        container.style.bottom = '55px'; // Moved slightly above the red progress bar
        container.style.width = '100%';
        container.style.height = '30px'; // Height of your vertical bars
        container.style.pointerEvents = 'none'; // Let clicks pass through the container itself
        container.style.zIndex = '1000';

        // 2. Container for the repeating "ghost" bars
        const ghostContainer = document.createElement('div');
        ghostContainer.style.position = 'absolute';
        ghostContainer.style.width = '100%';
        ghostContainer.style.height = '100%';

        const primaryBar = document.createElement('div');
        primaryBar.style.position = 'absolute';
        primaryBar.style.width = '0';
        primaryBar.style.height = '0';
        primaryBar.style.borderLeft = '8px solid transparent';
        primaryBar.style.borderRight = '8px solid transparent';
        primaryBar.style.borderTop = '20px solid #ffffff'; // Downward white arrow
        primaryBar.style.backgroundColor = 'transparent';
        primaryBar.style.left = '0%';
        primaryBar.style.transform = 'translateX(-50%)'; // Center it on the cursor

        const timeLabel = document.createElement('div');
        timeLabel.style.position = 'absolute';
        timeLabel.style.top = '-50px'; // Raised higher above the arrow
        timeLabel.style.left = '50%';
        timeLabel.style.transform = 'translateX(-50%)';
        timeLabel.style.backgroundColor = 'rgba(0,0,0,0.7)';
        timeLabel.style.color = '#fff';
        timeLabel.style.padding = '4px 8px';
        timeLabel.style.borderRadius = '4px';
        timeLabel.style.fontSize = '12px';
        timeLabel.style.fontFamily = 'monospace';
        timeLabel.style.whiteSpace = 'nowrap';
        timeLabel.innerText = '0.00s';
        
        primaryBar.appendChild(timeLabel);

        // 4. The Invisible Interactive Slider
        const slider = document.createElement('input');
        slider.type = 'range';
        slider.min = 0;
        slider.max = videoElement.duration;
        slider.value = 0;
        // Make it invisible but interactive
        slider.style.position = 'absolute';
        slider.style.width = '100%';
        slider.style.height = '100%';
        slider.style.top = '0';
        slider.style.left = '0';
        slider.style.margin = '0';
        slider.style.opacity = '0'; 
        slider.style.cursor = 'ew-resize';
        slider.style.pointerEvents = 'auto'; // Re-enable clicking for just the slider

        // Update slider max if the video duration changes (e.g., after an ad finishes)
        videoElement.addEventListener('durationchange', () => {
            if (!isNaN(videoElement.duration) && videoElement.duration > 0) {
                slider.max = videoElement.duration;
                // Force an update to redraw bars accurately for the new duration
                slider.dispatchEvent(new Event('input'));
            }
        });

        // 5. The Logic: Updating bars when the slider moves
        slider.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            const duration = videoElement.duration;
            const percentage = (val / duration) * 100;

            // Move the primary visual bar
            primaryBar.style.left = `${percentage}%`;
            
            // Update time label
            timeLabel.innerText = `${val.toFixed(2)}s`;

            // Clear out old ghost bars
            ghostContainer.innerHTML = '';

            // Prevent infinite loops if the slider is at 0 or a tiny fraction
            if (val > 1) { 
                let nextVal = val * 2;
                
                // Draw ghost bars until we exceed the video length
                while (nextVal <= duration) {
                    const ghostPercent = (nextVal / duration) * 100;
                    
                    const ghostBar = document.createElement('div');
                    ghostBar.style.position = 'absolute';
                    ghostBar.style.width = '0';
                    ghostBar.style.height = '0';
                    ghostBar.style.borderLeft = '8px solid transparent';
                    ghostBar.style.borderRight = '8px solid transparent';
                    ghostBar.style.borderTop = '20px solid #ffffff';
                    ghostBar.style.backgroundColor = 'transparent';
                    ghostBar.style.opacity = '0.4'; // Make them transparent
                    ghostBar.style.left = `${ghostPercent}%`;
                    ghostBar.style.transform = 'translateX(-50%)';
                    
                    ghostContainer.appendChild(ghostBar);
                    nextVal += val; // Increment by the original segment length
                }
            }

            console.log(`Segment length set to: ${val}s. Generated ${ghostContainer.children.length} recurring segments.`);
        });

        // 6. Aesthetic Buttons Container
        const videoPlayerContainer = document.querySelector('.html5-video-player') || document.body;
        
        // Remove existing button container if it somehow persisted
        const existingBtnContainer = document.getElementById('segment-btn-container');
        if (existingBtnContainer) existingBtnContainer.remove();

        const btnContainer = document.createElement('div');
        btnContainer.id = 'segment-btn-container';
        btnContainer.style.position = 'absolute';
        btnContainer.style.top = '20px';
        btnContainer.style.right = '20px';
        btnContainer.style.zIndex = '1000';
        btnContainer.style.display = 'flex';
        btnContainer.style.gap = '10px';

        // Save Checkpoint Button
        const saveBtn = document.createElement('button');
        saveBtn.innerText = 'Save Checkpoint';
        saveBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
        saveBtn.style.backdropFilter = 'blur(10px)';
        saveBtn.style.WebkitBackdropFilter = 'blur(10px)';
        saveBtn.style.border = '1px solid rgba(255, 255, 255, 0.3)';
        saveBtn.style.color = 'white';
        saveBtn.style.padding = '10px 20px';
        saveBtn.style.borderRadius = '20px';
        saveBtn.style.cursor = 'pointer';
        saveBtn.style.fontFamily = '"Roboto", Arial, sans-serif';
        saveBtn.style.fontSize = '14px';
        saveBtn.style.fontWeight = 'bold';
        saveBtn.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
        saveBtn.style.transition = 'all 0.2s ease';

        saveBtn.onmouseover = () => {
            saveBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.3)';
            saveBtn.style.transform = 'scale(1.05)';
        };
        saveBtn.onmouseout = () => {
            saveBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
            saveBtn.style.transform = 'scale(1)';
        };

        saveBtn.onclick = () => {
            const val = parseFloat(slider.value).toFixed(2);
            navigator.clipboard.writeText(val).then(() => {
                const originalText = saveBtn.innerText;
                saveBtn.innerText = `Copied: ${val}s!`;
                saveBtn.style.backgroundColor = 'rgba(76, 175, 80, 0.5)';
                saveBtn.style.borderColor = 'rgba(76, 175, 80, 0.8)';
                setTimeout(() => {
                    saveBtn.innerText = originalText;
                    saveBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
                    saveBtn.style.borderColor = 'rgba(255, 255, 255, 0.3)';
                }, 2000);
            });

            // Send checkpoint time to the Python server via WebSocket
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(val);
            } else {
                console.error('WebSocket not connected. Could not send checkpoint.');
            }
        };

        // Close (X) Button
        const closeBtn = document.createElement('button');
        closeBtn.innerText = '✕';
        closeBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
        closeBtn.style.backdropFilter = 'blur(10px)';
        closeBtn.style.WebkitBackdropFilter = 'blur(10px)';
        closeBtn.style.border = '1px solid rgba(255, 255, 255, 0.3)';
        closeBtn.style.color = 'white';
        closeBtn.style.padding = '10px 15px';
        closeBtn.style.borderRadius = '20px';
        closeBtn.style.cursor = 'pointer';
        closeBtn.style.fontFamily = '"Roboto", Arial, sans-serif';
        closeBtn.style.fontSize = '14px';
        closeBtn.style.fontWeight = 'bold';
        closeBtn.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
        closeBtn.style.transition = 'all 0.2s ease';

        closeBtn.onmouseover = () => {
            closeBtn.style.backgroundColor = 'rgba(255, 80, 80, 0.5)'; // Slight red tint on hover
            closeBtn.style.transform = 'scale(1.05)';
        };
        closeBtn.onmouseout = () => {
            closeBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
            closeBtn.style.transform = 'scale(1)';
        };

        closeBtn.onclick = () => {
            // Send 'no' to Python server via WebSocket
            if (ws.readyState === WebSocket.OPEN) {
                ws.send('no');
            } else {
                console.error('WebSocket not connected. Could not send cancel signal.');
            }

            if (container) container.remove();
            if (btnContainer) btnContainer.remove();
        };

        btnContainer.appendChild(saveBtn);
        btnContainer.appendChild(closeBtn);
        videoPlayerContainer.appendChild(btnContainer);

        // Append everything to the DOM
        container.appendChild(ghostContainer);
        container.appendChild(primaryBar);
        container.appendChild(slider);
        playerControls.appendChild(container);
    }
}

window.addEventListener('yt-navigate-finish', () => {
    setTimeout(injectSegmentSlider, 1000); 
});

setTimeout(injectSegmentSlider, 1500);