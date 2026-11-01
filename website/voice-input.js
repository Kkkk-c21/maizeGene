
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

        let recognition = null;
        let listening = false;

        button.addEventListener("click", function () {

            if (listening && recognition) {
                recognition.stop();
                return;
            }

            const SpeechRecognition =
                window.SpeechRecognition ||
                window.webkitSpeechRecognition;

            if (!SpeechRecognition) {
                alert("当前浏览器不支持语音识别，请使用最新版 Edge 或 Chrome。");
                return;
            }

            recognition = new SpeechRecognition();

            // Chinese speech recognition
            recognition.lang = "en-US";
            recognition.continuous = true;
            recognition.interimResults = true;

            const originalText = input.value.trim();

            recognition.onstart = function () {
                listening = true;
                button.textContent = "⏹";
                button.classList.add("is-listening");
                button.title = "点击停止录音";
            };

            recognition.onresult = function (event) {
                let transcript = "";

                for (let i = 0; i < event.results.length; i++) {
                    transcript += event.results[i][0].transcript;
                }

                input.value = [
                    originalText,
                    transcript.trim()
                ].filter(Boolean).join(" ");

                input.dispatchEvent(
                    new Event("input", { bubbles: true })
                );
            };

            recognition.onerror = function (event) {
                if (event.error === "not-allowed") {
                    alert("请允许浏览器使用麦克风。");
                } else if (
                    event.error !== "no-speech" &&
                    event.error !== "aborted"
                ) {
                    alert("语音识别出现问题：" + event.error);
                }
            };

            recognition.onend = function () {
                listening = false;
                button.textContent = "🎤";
                button.classList.remove("is-listening");
                button.title = "开始语音输入";
            };

            try {
                recognition.start();
            } catch (error) {
                alert("无法启动语音识别，请稍后重试。");
            }
        });
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
