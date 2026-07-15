from flask import Flask, render_template_string, request, jsonify
from chatbot import ADPreferenceChatbot
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize chatbot once
chatbot = None


def get_chatbot():
    global chatbot
    if chatbot is None:
        chatbot = ADPreferenceChatbot()
        if not chatbot.initialize():
            print("Warning: Failed to initialize chatbot. Check your database configuration.")
    return chatbot


# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AD Preference Chatbot</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .chat-container {
            width: 90%;
            max-width: 900px;
            height: 85vh;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .chat-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .chat-header h1 { font-size: 1.5em; margin-bottom: 5px; }
        .chat-header p { font-size: 0.9em; opacity: 0.9; }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f7fafc;
        }
        .message {
            margin-bottom: 15px;
            display: flex;
            animation: fadeIn 0.3s ease-in;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .user-message { justify-content: flex-end; }
        .bot-message { justify-content: flex-start; }
        .message-content {
            max-width: 70%;
            padding: 12px 18px;
            border-radius: 18px;
            line-height: 1.4;
        }
        .user-message .message-content {
            background: #4299e1;
            color: white;
            border-bottom-right-radius: 4px;
        }
        .bot-message .message-content {
            background: white;
            color: #2d3748;
            border: 1px solid #e2e8f0;
            border-bottom-left-radius: 4px;
        }
        .chat-input-container {
            padding: 20px;
            background: white;
            border-top: 1px solid #e2e8f0;
            display: flex;
            gap: 10px;
        }
        .chat-input {
            flex: 1;
            padding: 12px;
            border: 2px solid #e2e8f0;
            border-radius: 10px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.3s;
        }
        .chat-input:focus { border-color: #4299e1; }
        .send-button {
            padding: 12px 24px;
            background: #4299e1;
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-weight: bold;
            transition: background 0.3s;
        }
        .send-button:hover { background: #3182ce; }
        .send-button:disabled { background: #a0aec0; cursor: not-allowed; }
        .loading {
            display: none;
            text-align: center;
            padding: 10px;
            color: #718096;
        }
        .status-bar {
            padding: 10px 20px;
            background: #edf2f7;
            border-top: 1px solid #e2e8f0;
            font-size: 12px;
            color: #718096;
            display: flex;
            justify-content: space-between;
        }
        .status-online { color: #48bb78; }
        .status-offline { color: #f56565; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>🤖 AD Preference Chatbot</h1>
            <p>Ask me about campaigns, hype metrics, and company performance!</p>
        </div>
        <div class="chat-messages" id="chatMessages">
            <div class="message bot-message">
                <div class="message-content">
                    👋 Hello! I'm your AD Preference assistant.<br><br>
                    I can help you with:<br>
                    • Company campaign performance<br>
                    • Hype metrics and trends<br>
                    • Date-based AD preferences<br>
                    • Comparing different companies<br><br>
                    <strong>Try asking:</strong><br>
                    - "Which company has the most active campaigns?"<br>
                    - "Show me hype trends"<br>
                    - "Compare campaign performance"
                </div>
            </div>
        </div>
        <div class="loading" id="loading">🤔 Processing your question...</div>
        <div class="chat-input-container">
            <input type="text" class="chat-input" id="messageInput" placeholder="Type your question here..." onkeypress="handleKeyPress(event)">
            <button class="send-button" id="sendButton" onclick="sendMessage()">Send</button>
        </div>
        <div class="status-bar">
            <span id="status">🟢 Initializing...</span>
            <span>💡 Tip: Ask about specific companies or campaigns</span>
        </div>
    </div>

    <script>
        const chatMessages = document.getElementById('chatMessages');
        const messageInput = document.getElementById('messageInput');
        const loading = document.getElementById('loading');
        const sendButton = document.getElementById('sendButton');
        const statusSpan = document.getElementById('status');

        // Check status on load
        async function checkStatus() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                if (data.database_connected) {
                    statusSpan.innerHTML = '🟢 Database Connected';
                    statusSpan.className = 'status-online';
                } else {
                    statusSpan.innerHTML = '🔴 Database Disconnected';
                    statusSpan.className = 'status-offline';
                }
            } catch (error) {
                statusSpan.innerHTML = '🔴 Connection Error';
                statusSpan.className = 'status-offline';
            }
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter' && !sendButton.disabled) {
                sendMessage();
            }
        }

        function addMessage(content, isUser) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
            messageDiv.innerHTML = `<div class="message-content">${content}</div>`;
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;

            messageInput.value = '';
            addMessage(message, true);

            loading.style.display = 'block';
            sendButton.disabled = true;

            try {
                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ query: message })
                });

                const data = await response.json();
                loading.style.display = 'none';
                addMessage(data.response, false);

            } catch (error) {
                loading.style.display = 'none';
                addMessage('❌ Sorry, an error occurred. Please make sure the server is running and try again.', false);
            } finally {
                sendButton.disabled = false;
                messageInput.focus();
            }
        }

        // Check status every 10 seconds
        checkStatus();
        setInterval(checkStatus, 10000);
        messageInput.focus();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/health')
def health():
    bot = get_chatbot()
    return jsonify({
        "status": "healthy",
        "database_connected": bot.db_manager.connection is not None if bot else False
    })


@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    question = data.get('query', '')

    bot = get_chatbot()
    if not bot:
        return jsonify({"response": "Chatbot not initialized. Please check your configuration."})

    try:
        result = bot.process_question(question)
        return jsonify({
            "response": result['response'],
            "sql_query": result.get('sql_query'),
            "sql_results": result.get('sql_results', []),
        })
    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"})


if __name__ == '__main__':
    print("=" * 50)
    print("🤖 AD Preference Chatbot Starting...")
    print("=" * 50)
    print("\nPlease ensure your .env file has the correct:")
    print("  • Database credentials")
    print("  • OpenAI API key (optional, will work in demo mode)")
    print("\nStarting server at: http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    print("=" * 50)

    app.run(debug=False, host='0.0.0.0', port=5000)