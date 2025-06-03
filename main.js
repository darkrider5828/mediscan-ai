// static/js/main.js
// (v1.4 - Added Detailed Logging for marked.js Execution)

document.addEventListener('DOMContentLoaded', () => {
    // --- Get DOM Elements ---
    const uploadForm = document.getElementById('upload-form');
    const analyzeForm = document.getElementById('analyze-form');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    // chatHistory is fetched dynamically in appendChatMessage
    const visualizeBtn = document.getElementById('visualize-btn');
    const visualizationsDiv = document.getElementById('visualizations');
    const visualizationContent = document.getElementById('visualization-content');
    const statusMessages = document.getElementById('status-messages');
    const resetForm = document.getElementById('reset-form');

    // Spinners
    const loadingSpinner = document.getElementById('loading-spinner');
    const actionSpinner = document.getElementById('action-spinner');
    const chatSpinner = document.getElementById('chat-spinner');
    const vizSpinner = document.getElementById('visualization-spinner');

    // Result areas & Controls
    const analysisResultsDiv = document.getElementById('analysis-results');
    const postProcessingSection = document.getElementById('post-processing-section');
    const chatSection = document.getElementById('chat-section');

    // --- Helper: Show/Hide Spinners ---
    function showSpinner(spinnerElement, text = 'Working...') {
        if (spinnerElement) {
            spinnerElement.style.display = 'flex';
            const textNode = spinnerElement.childNodes[1];
             if(textNode && textNode.nodeType === Node.TEXT_NODE) {
                 textNode.textContent = ` ${text}`;
            }
        } else { console.warn("Attempted to show spinner, but element was null:", spinnerElement); }
    }
    function hideSpinner(spinnerElement) {
        if (spinnerElement) { spinnerElement.style.display = 'none'; }
        else { console.warn("Attempted to hide spinner, but element was null:", spinnerElement); }
    }

     // --- Helper: Disable/Enable Controls ---
    const uploadControls = '#upload-form button, #upload-form input';
    const actionControls = '#post-processing-section button, #post-processing-section a';
    const chatControls = '#chat-form button, #chat-form input';
    const allMainControls = [uploadControls, actionControls, chatControls, '#reset-form button'].join(', ');

    function setControlsDisabled(disabled) {
        document.querySelectorAll(allMainControls).forEach(el => {
            el.disabled = disabled;
            el.classList.toggle('disabled-look', disabled);
        });
    }

    // --- Initialization ---
    hideSpinner(loadingSpinner);
    hideSpinner(actionSpinner);
    hideSpinner(chatSpinner);
    hideSpinner(vizSpinner);
    if (visualizeBtn && visualizationsDiv) {
        setVisualizeButtonState(visualizationsDiv.style.display !== 'none');
    }


    // --- Upload Form Handling ---
    // Keep commented out
    /*
    if (uploadForm) { uploadForm.addEventListener('submit', () => { ... }); }
    */


     // --- Analyze Form Handling ---
    if (analyzeForm) {
         analyzeForm.addEventListener('submit', () => {
             showSpinner(actionSpinner, 'Generating Analysis...');
             setControlsDisabled(true);
             if(analysisResultsDiv) analysisResultsDiv.style.display = 'none';
             if(visualizationsDiv) visualizationsDiv.style.display = 'none';
         });
     }

    // --- Reset Form Handling ---
     if (resetForm) {
        resetForm.addEventListener('submit', (e) => {
            showSpinner(loadingSpinner, 'Resetting Session...');
            setControlsDisabled(true);
        });
    }


    // --- Chat Functionality ---
    if (chatForm && chatInput && chatSpinner) {
        console.log("Chat listener attaching...");
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault(); console.log("Chat submitted.");
            if (!chatInput) { console.error("Chat input missing!"); return; }
            const userQuery = chatInput.value.trim(); console.log("Query:", userQuery);
            if (!userQuery) { console.log("Empty query."); return; }

            // Append USER msg
            console.log("Appending USER message...");
            try { appendChatMessage(userQuery, 'user'); console.log("Append USER call finished."); }
            catch (appendError) { console.error("!!! Append USER Error:", appendError); try { appendChatMessage("Err display.", 'error'); } catch (e) {} }

            chatInput.value = ''; console.log("Input cleared.");
            showSpinner(chatSpinner, 'Thinking...');
            document.querySelectorAll(chatControls).forEach(el => el.disabled = true);
            console.log("Controls disabled.");

            // Fetch call
            try {
                console.log("Fetching /chat...");
                const response = await fetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: userQuery }), });
                console.log("Fetch response status:", response.status);

                const contentType = response.headers.get("content-type");
                if (response.ok && contentType && contentType.includes("application/json")) {
                    const data = await response.json(); console.log("Parsed JSON:", data);
                    if (data.error) { console.error('Chat App Error:', data.error); appendChatMessage(`Error: ${data.error}`, 'error'); }
                    else if (data.response) { appendChatMessage(data.response, 'assistant'); } // Append ASSISTANT
                    else { console.error('Unexpected JSON:', data); appendChatMessage(`Error: Unexpected server data.`, 'error'); }
                } else { // Handle non-OK or non-JSON
                    let errorMsg = `Request failed: ${response.status} (${response.statusText||'Unknown'})`; let responseText = '';
                    try { responseText = await response.text(); console.error('Non-JSON Response (start):', responseText.substring(0, 500));
                        if (responseText.trim().match(/<(!DOCTYPE|html|body|head|title|pre)/i)) { errorMsg += ". Server sent HTML (check server logs)."; }
                        else if (responseText.length > 0) { errorMsg += `. Server Response: ${responseText.substring(0,100)}...`; }
                        else { errorMsg += `. Server sent empty response.`; }
                    } catch (textError) { console.error('Cannot read response text:', textError); errorMsg += ". Cannot read error body."; }
                    console.error('Chat Error:', errorMsg); appendChatMessage(`Error: ${errorMsg}`, 'error');
                }
            } catch (error) { console.error('Chat Fetch/Network Error:', error); appendChatMessage(`Network error: ${error.message}.`, 'error');
            } finally {
                console.log("Hiding spinner, enabling controls."); hideSpinner(chatSpinner);
                document.querySelectorAll(chatControls).forEach(el => el.disabled = false);
                if (chatInput) chatInput.focus();
            }
        });
        console.log("Chat listener attached.");
    } else { /* Log missing elements */ }

    // --- Function to add messages to the chat history ---
     function appendChatMessage(message, role) {
        const functionStartLog = `APPENDING: Role='${role}', Message='${String(message).substring(0,50)}...'`;
        console.log(functionStartLog);

        const chatHistory = document.getElementById('chat-history');
        if (!chatHistory) { console.error("CRITICAL: #chat-history not found!"); return; }

        try {
            const messageDiv = document.createElement('div');
            messageDiv.classList.add('chat-message', role);

            const roleLabel = document.createElement('span');
            roleLabel.classList.add('role-label');
            roleLabel.textContent = role.charAt(0).toUpperCase() + role.slice(1) + ': ';

            const messageContent = document.createElement('span');
            messageContent.classList.add('message-content');

            // --- DETAILED MARKED.JS CHECK ---
            console.log("Checking for marked library...");
            if (typeof marked === 'function') {
                 console.log("✔️ marked.js found! Parsing message...");
                 const rawMarkdown = String(message);
                 // console.log("Raw Markdown:", rawMarkdown); // Uncomment to see raw input
                 const parsedHtml = marked.parse(rawMarkdown, { breaks: true, gfm: true });
                 // console.log("Parsed HTML:", parsedHtml); // Uncomment to see parsed output
                 messageContent.innerHTML = parsedHtml;
                 console.log("Assigned parsed HTML to innerHTML.");
            } else {
                console.warn("⚠️ marked.js NOT found! Using basic newline replacement.");
                // Fallback
                messageContent.innerHTML = String(message).replace(/\n/g, '<br>');
            }
            // --- END MARKED.JS CHECK ---

            messageDiv.appendChild(roleLabel);
            messageDiv.appendChild(messageContent);

            chatHistory.appendChild(messageDiv);
            console.log("Message div appended.");

            setTimeout(() => {
                 chatHistory.scrollTo({ top: chatHistory.scrollHeight, behavior: 'smooth' });
                 // console.log("Scrolled chat."); // Less verbose scroll log
            }, 50);

        } catch (error) {
            console.error(`!!! Error inside appendChatMessage for role ${role}:`, error);
        }
         console.log(`Finished appendChatMessage for role ${role}.`); // Log function end
    }


    // --- Visualization Toggle (Keep as is) ---
    if (visualizeBtn && visualizationsDiv && visualizationContent && vizSpinner) {
        visualizeBtn.addEventListener('click', async () => {
            const isHidden = visualizationsDiv.style.display === 'none' || visualizationsDiv.style.display === '';
            if (isHidden) {
                visualizationsDiv.style.display = 'block'; visualizationContent.innerHTML = '';
                showSpinner(vizSpinner, 'Loading Visualizations...'); setControlsDisabled(true);
                try {
                    const response = await fetch('/visualize'); const data = await response.json();
                    if (!response.ok) throw new Error(data?.error || `Failed (Status: ${response.status})`);
                    if (data.error && data.error.includes("Kaleido missing")) {
                         visualizationContent.innerHTML = `<div class="alert alert-warning">Viz Error: Kaleido package missing on server.</div>`;
                         console.error("Kaleido missing."); setVisualizeButtonState(true); return;
                    }
                    if (data.error) throw new Error(data.error);

                    if (data.plots && Object.keys(data.plots).length > 0) {
                        for (const title in data.plots) {
                            const plotContainer = document.createElement('div'); plotContainer.classList.add('visualization-item');
                            const titleEl = document.createElement('h4'); titleEl.textContent = title;
                            if (typeof data.plots[title] === 'string' && data.plots[title].startsWith('Error:')) {
                                 const errorEl = document.createElement('p'); errorEl.classList.add('alert', 'alert-danger');
                                 errorEl.textContent = data.plots[title]; plotContainer.appendChild(titleEl); plotContainer.appendChild(errorEl);
                            } else {
                                const img = document.createElement('img'); img.src = `data:image/png;base64,${data.plots[title]}`; img.alt = title;
                                plotContainer.appendChild(titleEl); plotContainer.appendChild(img);
                            }
                            visualizationContent.appendChild(plotContainer);
                        }
                        setVisualizeButtonState(true);
                    } else { visualizationContent.innerHTML = `<p class="info-text">${data.message || 'No visualizations.'}</p>`; setVisualizeButtonState(true); }
                } catch (error) { console.error('Viz Load Error:', error); visualizationContent.innerHTML = `<div class="alert alert-danger">Error loading visuals: ${error.message}</div>`;
                } finally { hideSpinner(vizSpinner); setControlsDisabled(false); }
            } else { visualizationsDiv.style.display = 'none'; visualizationContent.innerHTML = ''; setVisualizeButtonState(false); }
        });
    }
    function setVisualizeButtonState(isVisible) { if (!visualizeBtn) return; if (isVisible) visualizeBtn.innerHTML = '<span class="icon">📉</span> Hide Visuals'; else visualizeBtn.innerHTML = '<span class="icon">📈</span> Show Visuals'; }

}); // End DOMContentLoaded