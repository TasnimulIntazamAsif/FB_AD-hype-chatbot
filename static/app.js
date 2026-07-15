// Chatbot Frontend Controller
document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const dbStatusBadge = document.getElementById("db-status-badge");
    const openaiStatusBadge = document.getElementById("openai-status-badge");
    const chatMessages = document.getElementById("chat-messages");
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-btn");
    const clearChatBtn = document.getElementById("clear-chat-btn");
    const suggestionChips = document.getElementById("suggestion-chips");
    const schemaTree = document.getElementById("schema-tree");
    const inspectorSql = document.getElementById("inspector-sql");
    const inspectorDataContainer = document.getElementById("inspector-data-container");
    const copySqlBtn = document.getElementById("copy-sql-btn");

    let appStatus = { dbConnected: false, openaiConfigured: false };

    // Set up default welcome message
    showWelcomeMessage();

    // Check Backend Connection Status
    async function checkStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();
            
            appStatus.dbConnected = data.database.connected;
            appStatus.openaiConfigured = data.openai.configured;

            // Update DB badge
            dbStatusBadge.className = "status-badge";
            if (data.database.connected) {
                dbStatusBadge.classList.add("status-connected");
                dbStatusBadge.querySelector("span:last-child").textContent = `PostgreSQL: Connected (${data.database.database_name})`;
                dbStatusBadge.title = `Host: ${data.database.host}\nDatabase: ${data.database.database_name}`;
            } else {
                dbStatusBadge.classList.add("status-disconnected");
                dbStatusBadge.querySelector("span:last-child").textContent = "PostgreSQL: Disconnected";
                dbStatusBadge.title = data.database.message;
            }

            // Update OpenAI badge
            openaiStatusBadge.className = "status-badge";
            if (data.openai.configured) {
                openaiStatusBadge.classList.add("status-connected");
                openaiStatusBadge.querySelector("span:last-child").textContent = `OpenAI: Active (${data.openai.model})`;
                openaiStatusBadge.title = `Model: ${data.openai.model}`;
            } else {
                openaiStatusBadge.classList.add("status-disconnected");
                openaiStatusBadge.querySelector("span:last-child").textContent = "OpenAI: Missing API Key";
                openaiStatusBadge.title = "Please enter an OPENAI_API_KEY in the .env file.";
            }

            // Update suggestions based on status
            renderSuggestionChips();
            
        } catch (error) {
            console.error("Error fetching status:", error);
            dbStatusBadge.className = "status-badge status-disconnected";
            dbStatusBadge.querySelector("span:last-child").textContent = "Server: Unreachable";
            openaiStatusBadge.className = "status-badge status-disconnected";
            openaiStatusBadge.querySelector("span:last-child").textContent = "Server: Unreachable";
        }
    }

    // Fetch and Render Database Schema
    async function fetchSchema() {
        try {
            const res = await fetch("/api/schema");
            const schema = await res.json();
            
            schemaTree.innerHTML = "";
            const tables = Object.keys(schema);
            
            if (tables.length === 0) {
                schemaTree.innerHTML = `<p class="placeholder-text">No tables found in public schema.</p>`;
                return;
            }

            tables.forEach(table => {
                const tableItem = document.createElement("div");
                tableItem.className = "schema-table-item";
                
                const tableName = document.createElement("div");
                tableName.className = "schema-table-name";
                tableName.textContent = table;
                tableName.addEventListener("click", () => {
                    columnsList.style.display = columnsList.style.display === "none" ? "flex" : "none";
                });

                const columnsList = document.createElement("div");
                columnsList.className = "schema-columns-list";
                
                schema[table].forEach(col => {
                    const colItem = document.createElement("div");
                    colItem.className = "schema-column-item";
                    colItem.innerHTML = `${col.column_name} <span class="data-type">${col.data_type}</span>`;
                    columnsList.appendChild(colItem);
                });

                tableItem.appendChild(tableName);
                tableItem.appendChild(columnsList);
                schemaTree.appendChild(tableItem);
            });
        } catch (error) {
            console.error("Error fetching schema:", error);
            schemaTree.innerHTML = `<p class="placeholder-text" style="color:var(--error)">Failed to load schema.</p>`;
        }
    }

    // Render suggestion prompts
    function renderSuggestionChips() {
        suggestionChips.innerHTML = "";
        
        const liveSuggestions = [
            { en: "Who campaign the most?", bn: "কোন কোম্পানি সবচেয়ে বেশি ক্যাম্পেইন করছে?" },
            { en: "Show top ads by hype score", bn: "সবচেয়ে বেশি হাইপ কার বিজ্ঞাপনে?" },
            { en: "Hype comparison date wise", bn: "তারিখ অনুযায়ী বিজ্ঞাপনের হাইপ কেমন?" },
            { en: "Show campaigns platform-wise", bn: "প্ল্যাটফর্ম অনুযায়ী ক্যাম্পেইনগুলো দেখাও" }
        ];

        liveSuggestions.forEach(sug => {
            const chip = document.createElement("button");
            chip.className = "chip";
            chip.textContent = sug.bn;
            chip.addEventListener("click", () => {
                userInput.value = sug.bn;
                userInput.focus();
            });
            suggestionChips.appendChild(chip);
        });
    }

    // Show initial welcome system prompt
    function showWelcomeMessage() {
        chatMessages.innerHTML = "";
        
        let introHTML = `
            <div class="message message-bot">
                <div class="message-sender">AD Hype Assistant</div>
                <div class="message-bubble">
                    <p><strong>হ্যালো! আমি আপনার বিজ্ঞাপন (AD) ও ক্যাম্পেইন সংক্রান্ত এআই সহকারী।</strong></p>
                    <p>আমি আপনার PostgreSQL ডেটাবেসের টেবিলগুলো বিশ্লেষণ করে সরাসরি উত্তর দিতে পারি।</p>
                    
                    <div class="setup-guide-box" style="margin-top: 10px;">
                        <h4>⚠️ ডেটাবেস ও এপিআই সংযোগ গাইড (Connection Guide)</h4>
                        <p>১. প্রজেক্টের মূল ফোল্ডারে <code>.env</code> ফাইলটি তৈরি করুন (উদাহরণ হিসেবে <code>.env.example</code> ব্যবহার করুন)।</p>
                        <p>২. আপনার <code>OPENAI_API_KEY</code> এবং PostgreSQL ডেটাবেসের সংযোগের তথ্য দিন।</p>
                        <p>৩. সংযোগ না থাকা অবস্থায় সিস্টেমটি <strong>সিমুলেশন মোড (Simulation Mode)</strong> এ ডামি ডেটা নিয়ে কাজ করবে, যাতে আপনি অ্যাপটির ডিজাইন পরীক্ষা করতে পারেন।</p>
                    </div>
                    
                    <p>নিচের যেকোনো প্রম্পটে ক্লিক করে পরীক্ষা করুন অথবা নিজে যেকোনো প্রশ্ন বাংলায় বা ইংরেজিতে লিখুন।</p>
                </div>
            </div>
        `;
        chatMessages.innerHTML = introHTML;
    }

    // Clean / Parse Markdown to HTML
    function formatMarkdown(text) {
        if (!text) return "";
        
        // Escape HTML
        let escaped = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Code block formatting
        escaped = escaped.replace(/```(json|sql|html|javascript)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
            
        // Bold formatting
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Inline code formatting
        escaped = escaped.replace(/`(.*?)`/g, '<code>$1</code>');
        
        // Lists and Paragraph separation
        let lines = escaped.split("\n");
        let output = [];
        let inList = false;
        
        for (let line of lines) {
            let trimmed = line.trim();
            if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
                if (!inList) {
                    output.push("<ul style='margin-left: 20px; margin-bottom: 8px;'>");
                    inList = true;
                }
                output.push("<li style='margin-bottom: 4px;'>" + trimmed.substring(2) + "</li>");
            } else {
                if (inList) {
                    output.push("</ul>");
                    inList = false;
                }
                if (trimmed) {
                    output.push("<p style='margin-bottom: 8px;'>" + trimmed + "</p>");
                } else {
                    output.push("<div style='height: 6px;'></div>");
                }
            }
        }
        if (inList) output.push("</ul>");
        
        return output.join("");
    }

    // Append Message to Thread
    function appendMessage(sender, text, isUser = false) {
        const messageDiv = document.createElement("div");
        messageDiv.className = `message ${isUser ? "message-user" : "message-bot"}`;
        
        const senderDiv = document.createElement("div");
        senderDiv.className = "message-sender";
        senderDiv.textContent = sender;

        const bubbleDiv = document.createElement("div");
        bubbleDiv.className = "message-bubble";
        bubbleDiv.innerHTML = isUser ? `<p>${text}</p>` : formatMarkdown(text);
        
        messageDiv.appendChild(senderDiv);
        messageDiv.appendChild(bubbleDiv);
        chatMessages.appendChild(messageDiv);
        
        // Auto scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Render Data Table in SQL Results Inspector
    function renderDataTable(results) {
        inspectorDataContainer.innerHTML = "";
        
        if (!results || results.length === 0) {
            inspectorDataContainer.innerHTML = `<p class="placeholder-text">Query returned no records (0 rows).</p>`;
            return;
        }

        const table = document.createElement("table");
        table.className = "data-table";

        // Headers
        const headerRow = document.createElement("tr");
        const keys = Object.keys(results[0]);
        keys.forEach(key => {
            const th = document.createElement("th");
            th.textContent = key;
            headerRow.appendChild(th);
        });
        table.appendChild(headerRow);

        // Rows
        results.forEach(row => {
            const tr = document.createElement("tr");
            keys.forEach(key => {
                const td = document.createElement("td");
                td.textContent = row[key] !== null ? row[key] : "NULL";
                tr.appendChild(td);
            });
            table.appendChild(tr);
        });

        inspectorDataContainer.appendChild(table);
    }

    // Chat Submission Form Handler
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const prompt = userInput.value.trim();
        if (!prompt) return;

        // Add user message
        appendMessage("You", prompt, true);
        userInput.value = "";
        
        // Disable input during request
        userInput.disabled = true;
        sendBtn.disabled = true;

        // Append typing indicator
        const typingIndicator = document.createElement("div");
        typingIndicator.id = "temp-typing";
        typingIndicator.className = "message message-bot";
        typingIndicator.innerHTML = `
            <div class="message-sender">AD Hype Assistant</div>
            <div class="message-bubble typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        chatMessages.appendChild(typingIndicator);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: prompt })
            });

            // Remove typing indicator
            const tempNode = document.getElementById("temp-typing");
            if (tempNode) tempNode.remove();

            const data = await res.json();
            
            if (res.ok) {
                // Add chatbot response
                appendMessage("AD Hype Assistant", data.response);

                // Update SQL inspector
                if (data.sql_query) {
                    inspectorSql.textContent = data.sql_query;
                } else {
                    inspectorSql.textContent = "-- No SQL query generated.";
                }

                // Update results inspector table
                renderDataTable(data.sql_results);
            } else {
                // Render Backend Error
                appendMessage("AD Hype Assistant", data.response || `Error: ${data.error}`);
                if (data.sql_query) {
                    inspectorSql.textContent = data.sql_query;
                }
                renderDataTable([]);
            }
        } catch (error) {
            console.error("Chat error:", error);
            const tempNode = document.getElementById("temp-typing");
            if (tempNode) tempNode.remove();
            appendMessage("AD Hype Assistant", `সিস্টেমে সংযোগ করতে সমস্যা হয়েছে। দয়া করে নিশ্চিত করুন ব্যাকএন্ড সার্ভার সচল আছে।\n\n**Error:** ${error.message}`);
        } finally {
            userInput.disabled = false;
            sendBtn.disabled = false;
            userInput.focus();
            checkStatus();
        }
    });

    // Clear Chat Handler
    clearChatBtn.addEventListener("click", () => {
        showWelcomeMessage();
        inspectorSql.textContent = "-- Submit a query in the chat to see generated SQL";
        inspectorDataContainer.innerHTML = `<p class="placeholder-text">Execute a prompt to view data records.</p>`;
    });

    // Copy SQL Query Handler
    copySqlBtn.addEventListener("click", () => {
        const sqlText = inspectorSql.textContent;
        if (sqlText && !sqlText.startsWith("--")) {
            navigator.clipboard.writeText(sqlText)
                .then(() => {
                    const origSVG = copySqlBtn.innerHTML;
                    copySqlBtn.innerHTML = `<span style="font-size:10px;color:var(--success)">Copied!</span>`;
                    setTimeout(() => {
                        copySqlBtn.innerHTML = origSVG;
                    }, 1500);
                })
                .catch(err => {
                    console.error("Copy failed:", err);
                });
        }
    });

    // Initial check
    checkStatus();
    fetchSchema();
});
