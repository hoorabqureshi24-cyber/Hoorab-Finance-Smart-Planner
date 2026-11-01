document.addEventListener("DOMContentLoaded", function () {
    // Chatbot elements
    const chatToggle = document.getElementById("chatToggle");
    const chatWindow = document.getElementById("chatWindow");
    const closeChat = document.getElementById("closeChat");
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const chatMessages = document.getElementById("chatMessages");
    const micButton = document.getElementById("micButton");
    const voiceStatus = document.getElementById("voiceStatus");

    // Open chatbot
    if (chatToggle && chatWindow) {
        chatToggle.addEventListener("click", function () {
            chatWindow.hidden = !chatWindow.hidden;

            if (!chatWindow.hidden && chatInput) {
                chatInput.focus();
            }
        });
    }

    // Close chatbot
    if (closeChat && chatWindow) {
        closeChat.addEventListener("click", function () {
            chatWindow.hidden = true;
        });
    }

    // Display messages
    function addMessage(text, className) {
        if (!chatMessages) return;

        const message = document.createElement("div");
        message.className = "message " + className;
        message.textContent = text;

        chatMessages.appendChild(message);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Simple finance chatbot replies
    function getReply(message) {
        const text = message.toLowerCase();

        if (text.includes("budget")) {
            return "Create a monthly budget by adding your income, expenses, savings and financial goals.";
        }

        if (text.includes("save") || text.includes("saving")) {
            return "Try setting a monthly savings goal and record your expenses regularly.";
        }

        if (text.includes("expense") || text.includes("spend")) {
            return "Record every expense and compare your total spending with your planned budget.";
        }

        if (text.includes("income")) {
            return "Add all your income sources to calculate your available monthly budget.";
        }

        if (text.includes("hello") || text.includes("hi")) {
            return "Hello! I am your Finance Assistant. Ask me about budgeting, savings or expenses.";
        }

        return "I can help with basic budgeting, income, expenses and savings. What would you like to plan?";
    }

    // Send a chat message
    if (chatForm && chatInput) {
        chatForm.addEventListener("submit", function (event) {
            event.preventDefault();

            const message = chatInput.value.trim();
            if (!message) return;

            addMessage(message, "user-message");
            chatInput.value = "";

            const reply = getReply(message);

            setTimeout(function () {
                addMessage(reply, "bot-message");
            }, 300);
        });
    }

    // Voice input using browser speech recognition
    if (micButton) {
        micButton.addEventListener("click", function () {
            const SpeechRecognition =
                window.SpeechRecognition ||
                window.webkitSpeechRecognition;

            if (!SpeechRecognition) {
                if (voiceStatus) {
                    voiceStatus.textContent =
                        "Voice input is not supported in this browser. Try Chrome.";
                }
                return;
            }

            const recognition = new SpeechRecognition();
            recognition.lang = "en-US";
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;

            if (voiceStatus) {
                voiceStatus.textContent = "Listening...";
            }

            recognition.onresult = function (event) {
                const transcript =
                    event.results[0][0].transcript;

                if (chatInput) {
                    chatInput.value = transcript;
                    chatInput.focus();
                }

                if (voiceStatus) {
                    voiceStatus.textContent = "Voice captured. Press Send.";
                }
            };

            recognition.onerror = function () {
                if (voiceStatus) {
                    voiceStatus.textContent =
                        "Could not capture voice. Check microphone permission.";
                }
            };

            recognition.onend = function () {
                if (voiceStatus &&
                    voiceStatus.textContent === "Listening...") {
                    voiceStatus.textContent = "Voice input ended.";
                }
            };

            recognition.start();
        });
    }
});