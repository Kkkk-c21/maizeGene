
(function () {
    const INPUT_IDS = [
        "geneInput",
        "searchInput",
        "traitInput",
        "keyword",
        "question"
    ];

    // Add microphone button styles
    const style = document.createElement("style");
    style.textContent = `
        .voice-input-wrapper {
            position: relative;
            display: flex;
            flex: 1 1 auto;
            min-width: 0;
        }

        .voice-input-wrapper input,
        .voice-input-wrapper textarea {
            width: 100% !important;
            min-width: 0 !important;
            padding-right: 50px !important;
        }

        .voice-input-button {
            position: absolute;
            right: 8px;
            top: 50%;
            transform: translateY(-50%);
            width: 34px;
            height: 34px;
            border: 1px solid #d7e6db;
            border-radius: 8px;
            background: white;
            color: #287a48;
            cursor: pointer;
            font-size: 18px;
            z-index: 5;
            padding: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .voice-input-button.is-listening {
            background: #fff0f0;
            color: #c0392b;
        }
    `;
    document.head.appendChild(style);

    function setupVoiceInput(input) {
        if (!input || input.dataset.voiceReady) return;

        input.dataset.voiceReady = "true";

        const wrapper = document.createElement("div");
        wrapper.className = "voice-input-wrapper";

        input.parentElement.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        const button = document.createElement("button");
        button.type = "button";
        button.className = "voice-input-button";
        button.textContent = "🎤";
        button.title = "开始语音输入";
        wrapper.appendChild(button);

        let recorder, stream, timer;
        const status = document.createElement('span');
        status.setAttribute('role', 'status');
        status.style.cssText = 'position:absolute;top:100%;left:0;font-size:12px';
        wrapper.appendChild(status);
        button.title = 'Record English';
        button.textContent = '🎤';
        function reset() {
            clearTimeout(timer);
            if (stream) stream.getTracks().forEach(t => t.stop());
            button.disabled = false;
            button.classList.remove('is-listening');
            button.textContent = '🎤';
        }
        button.onclick = async () => {
            if (recorder && recorder.state === 'recording') { recorder.stop(); return; }
            button.disabled = true;
            try {
                if (!window.isSecureContext) throw Error('Microphone requires HTTPS or localhost.');
                if (!window.MediaRecorder || !navigator.mediaDevices) throw Error('Audio recording unavailable.');
                stream = await navigator.mediaDevices.getUserMedia({audio:true});
                const mime = ['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(t => MediaRecorder.isTypeSupported(t));
                recorder = new MediaRecorder(stream, mime ? {mimeType:mime} : undefined);
                const chunks = [];
                recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
                recorder.onerror = () => { reset(); status.textContent = 'Recording failed.'; };
                recorder.onstop = () => {
                    reset(); button.disabled = true;
                    const data = new FormData();
                    data.append('file',new Blob(chunks,{type:recorder.mimeType}),'recording');
                    const xhr = new XMLHttpRequest();
                    xhr.open('POST','/api/v1/audio/transcriptions');
                    xhr.timeout = 300000;
                    status.textContent = 'Uploading…';
                    xhr.upload.onload = () => { status.textContent = 'Transcribing English…'; };
                    xhr.onload = () => {
                        reset();
                        try {
                            const result = JSON.parse(xhr.responseText);
                            if (xhr.status !== 200) throw Error(result.detail || 'Transcription failed.');
                            input.value = result.text;
                            input.dispatchEvent(new Event('input',{bubbles:true}));
                            status.textContent = result.text ? 'Ready to edit and submit.' : 'No speech detected.';
                        } catch(e) { status.textContent = e.message; }
                    };
                    xhr.onerror = xhr.ontimeout = () => { reset(); status.textContent = 'Service unavailable. Please retry.'; };
                    xhr.send(data);
                };
                recorder.start();
                button.disabled = false;
                button.textContent = '■';
                button.classList.add('is-listening');
                status.textContent = 'Recording English… Click to stop (60 seconds maximum).';
                timer = setTimeout(() => { if(recorder.state === 'recording') recorder.stop(); },60000);
            } catch(e) { reset(); status.textContent = e.message; }
        };
    }
    function initVoiceInputs() {
        INPUT_IDS.forEach(function (id) {
            setupVoiceInput(document.getElementById(id));
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initVoiceInputs
        );
    } else {
        initVoiceInputs();
    }
})();
