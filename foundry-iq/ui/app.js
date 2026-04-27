// Foundry IQ — Chat UI for knowledge base agent
// Communicates with a local Python API server or falls back to mock responses.

const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const statusEl = document.getElementById("status");
const apiEndpointEl = document.getElementById("api-endpoint");

// ── Mock responses for offline/demo mode ─────

const MOCK_RESPONSES = {
    "real-time analytics":
        "Based on the knowledge base, **Microsoft Fabric** and **Azure AI Search** both support real-time analytics:\n\n" +
        "- **Microsoft Fabric** offers Eventstream for real-time ingestion, KQL Database/Eventhouse for high-velocity time-series analytics, and Data Activator for trigger-based automation.\n" +
        "- **Azure AI Search** provides hybrid search combining keyword and vector search for near real-time document discovery.\n\n" +
        "_Sources: product-fabric.md, product-ai-search.md_",
    "knowledge base":
        "**Azure AI Foundry** supports 6 types of knowledge sources:\n\n" +
        "1. **Azure AI Search Index** — enterprise-scale search\n" +
        "2. **Azure Blob Storage** — documents and files\n" +
        "3. **Web (Bing)** — real-time internet grounding\n" +
        "4. **Microsoft SharePoint (Remote)** — M365 governance-compliant\n" +
        "5. **Microsoft SharePoint (Indexed)** — custom search pipelines\n" +
        "6. **Microsoft OneLake** — unstructured Fabric data\n\n" +
        "_Source: product-ai-foundry.md_",
    "storage":
        "**Azure Blob Storage** is the recommended storage solution:\n\n" +
        "- Hot tier: ~$0.018/GB/month for frequently accessed data\n" +
        "- Cool tier: ~$0.01/GB/month for infrequent access\n" +
        "- Archive tier: ~$0.00099/GB/month for long-term retention\n\n" +
        "Key features include lifecycle management, immutable storage (WORM), versioning, and Data Lake Storage Gen2 for analytics.\n\n" +
        "_Source: product-blob-storage.md_",
    default:
        "Based on the available product documentation, I can help you with:\n\n" +
        "- **Azure AI Search** — enterprise search with vector/hybrid capabilities\n" +
        "- **Azure Blob Storage** — scalable object storage\n" +
        "- **Azure AI Foundry** — unified AI agent platform\n" +
        "- **Microsoft Fabric** — unified analytics platform\n" +
        "- **GitHub Copilot CLI** — AI-powered terminal assistance\n\n" +
        "What would you like to know more about?"
};

function getMockResponse(question) {
    const q = question.toLowerCase();
    for (const [key, response] of Object.entries(MOCK_RESPONSES)) {
        if (key !== "default" && q.includes(key)) {
            return response;
        }
    }
    return MOCK_RESPONSES.default;
}

// ── DOM helpers ──────────────────────────────

function addMessage(role, content) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    const inner = document.createElement("div");
    inner.className = "message-content";
    inner.textContent = content;
    // Simple markdown bold rendering
    inner.innerHTML = content
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>")
        .replace(/_(.+?)_/g, "<em>$1</em>");
    div.appendChild(inner);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
}

function addTypingIndicator() {
    const div = document.createElement("div");
    div.className = "message assistant";
    div.id = "typing";
    div.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function removeTypingIndicator() {
    const el = document.getElementById("typing");
    if (el) el.remove();
}

// ── API communication ────────────────────────

async function sendToApi(question) {
    const endpoint = apiEndpointEl.value.replace(/\/+$/, "");
    const response = await fetch(`${endpoint}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
    });

    if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
    }

    const data = await response.json();
    return data.answer || data.response || JSON.stringify(data);
}

// ── Chat handler ─────────────────────────────

async function handleSubmit(e) {
    e.preventDefault();
    const question = userInput.value.trim();
    if (!question) return;

    addMessage("user", question);
    userInput.value = "";
    sendBtn.disabled = true;
    addTypingIndicator();

    try {
        const answer = await sendToApi(question);
        removeTypingIndicator();
        addMessage("assistant", answer);
        statusEl.textContent = "Connected";
        statusEl.style.background = "#50C19B";
    } catch {
        // Fall back to mock responses in demo/offline mode
        removeTypingIndicator();
        await new Promise(r => setTimeout(r, 600)); // simulate thinking
        const mockAnswer = getMockResponse(question);
        addMessage("assistant", mockAnswer);
        statusEl.textContent = "Demo mode";
        statusEl.style.background = "#617595";
    }

    sendBtn.disabled = false;
    userInput.focus();
}

chatForm.addEventListener("submit", handleSubmit);

// Allow Enter to submit
userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event("submit"));
    }
});
