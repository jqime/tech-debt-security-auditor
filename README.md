# 🛡️ Tech Debt & Security Auditor

An elegant, automated DevSecOps dashboard and orchestration assistant. Built on **Antigravity** and powered by **OpenCode** (with free models like `opencode/zen`), it performs comprehensive static analysis, security auditing, and technical debt measurement, then compiles the results into a gorgeous, modern HTML report.

---

## ✨ Features

- **🔒 Advanced Security Scan**: Uncovers exposed secrets, hardcoded API keys, and vulnerable package dependencies.
- **📊 Technical Debt Measurement**: Analyzes cyclomatic complexity, code duplicates, and general maintainability.
- **🎨 Premium Visual Reports**: Consolidates raw JSON outputs into a responsive, highly interactive dark-themed HTML report using Google Fonts and CSS glassmorphic effects.
- **⚙️ Seamless Orchestration**: Simple workflow integration built on top of Antigravity rules and shell executors.

---

## 🚀 Quick Start

### 1. Prerequisites & Installation

Verify that Node.js, `npm`, and `opencode-ai` are installed on your system. If not, install the OpenCode CLI globally:

```bash
# Install the OpenCode CLI globally
npm install -g opencode-ai
```

### 2. Authenticating OpenCode (Free Plan)

Authenticate the CLI to connect to the free model hub:

```bash
opencode auth login
```

Verify that the CLI is functional:

```bash
opencode --version
```

### 3. Running an Audit

Audit any repository locally or remotely by running the master audit script:

```bash
./run-audit.sh https://github.com/octocat/Hello-World
```

Once the execution finishes, you can find the final executive HTML report under:
```bash
reports/executive-report.html
```
