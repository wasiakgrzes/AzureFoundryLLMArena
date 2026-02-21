1️⃣ Authentication Model (MVP)
------------------------------

### Constraints

*   All compared models must belong to **one Azure AI Foundry resource**
    
*   Authentication method: **API key**
    
*   API key loaded from environment variables
    
*   No API key in UI
    
*   No multiple resources supported in MVP
    

### Required Environment Variables

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   AZURE_FOUNDRY_ENDPOINT  AZURE_FOUNDRY_API_KEY   `

### Behavior

*   On app startup:
    
    *   Read endpoint + API key
        
    *   Initialize Foundry SDK client
        
    *   Fetch all deployments from that resource
        

If env vars are missing → fail fast with clear error.

2️⃣ Deployment Discovery (MVP)
==============================

### On App Startup

System must:

1.  Connect to Foundry using SDK
    
2.  Retrieve all available deployments
    
3.  Store:
    
    *   deployment name
        
    *   model name (if available)
        
    *   model type (chat/completion/etc.)
        
    *   any metadata needed
        

### Filtering

For MVP:

*   Only include **text-based inference models**
    
*   Ignore non-compatible types if needed
    

3️⃣ Model Selection UX
======================

### UI Behavior

*   After deployments are loaded:
    
    *   Present multi-select dropdown
        
    *   Allow selecting 1–5 deployments
        
*   Once selected:
    
    *   UI dynamically creates N output columns
        

4️⃣ Execution Flow (MVP Final)
==============================

Sequence:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   sequenceDiagram      participant User      participant UI      participant Controller      participant AzureFoundry      UI->>Controller: Load deployments at startup      Controller->>AzureFoundry: List deployments      AzureFoundry-->>Controller: Deployment list      User->>UI: Select deployments      User->>UI: Enter prompt      UI->>Controller: Submit prompt      loop for each selected deployment          Controller->>AzureFoundry: Inference request          AzureFoundry-->>Controller: Output + usage      end      Controller->>Controller:           - Calculate cost          - Measure latency          - Normalize response      Controller-->>UI: Results per model   `

5️⃣ Output Requirements (Per Column)
====================================

Each model column must show:

*   Deployment name
    
*   Raw output
    
*   Input tokens
    
*   Output tokens
    
*   Total tokens
    
*   Estimated cost
    
*   Latency (ms)
    
*   Error message if failure
    

No markdown parsing required.

6️⃣ Cost Calculation (MVP)
==========================

Cost must be:

*   Calculated locally
    
*   Based on token usage returned from SDK
    
*   Based on static pricing config (JSON or internal dictionary)
    

Example internal pricing structure:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "gpt-4": {      "input_per_1k": 0.01,      "output_per_1k": 0.03    }  }   `

Formula:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   cost = (input_tokens/1000 * input_price) +         (output_tokens/1000 * output_price)   `

7️⃣ Latency
===========

For each model:

*   Capture request start timestamp
    
*   Capture response timestamp
    
*   Compute latency\_ms
    

Must be displayed.

8️⃣ Failure Isolation
=====================

If deployment fails:

*   Show error message in its column
    
*   Continue processing other deployments
    

No global crash.

9️⃣ Export Best Model Configuration (New Addition)
==================================================

After comparison:

User can:

*   Select one model as “Best”
    
*   Click "Export Configuration"
    

Exported JSON must include:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "endpoint": "...",    "deployment_name": "...",    "api_type": "azure_foundry",    "inference_type": "chat",    "model_name": "...",    "pricing_reference": "...",    "export_timestamp": "..."  }   `

Important:

*   Do NOT export API key
    
*   Endpoint can be exported (non-sensitive)
    
*   API key remains environment-managed
    

Purpose:

*   This JSON can later be reused in REST-based production call.
    

🏗 Architecture Diagram (MVP Final)
===================================

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   graph TD  ENV[Environment Variables]  SDK[Azure Foundry SDK Client]  UI[Streamlit UI]  Controller[Comparison Controller]  Cost[Cost Calculator]  Normalizer[Response Normalizer]  ENV --> SDK  SDK --> Controller  UI --> Controller  Controller --> Cost  Controller --> Normalizer  Controller --> UI   `

🔐 Security Confirmation
========================

Since:

*   App runs locally
    
*   API key in environment only
    
*   Not stored in JSON
    
*   Not displayed in UI
    
*   Not exported
    

This is acceptable for MVP.

📌 Updated MVP Definition (Strict)
==================================

MVP must:

*   Load endpoint + API key from env
    
*   Auto-discover deployments at startup
    
*   Allow selecting 1–5 deployments
    
*   Accept single text prompt
    
*   Send same prompt to all selected models
    
*   Display side-by-side outputs
    
*   Show tokens, cost, latency
    
*   Isolate failures
    
*   Allow exporting selected best model config (without secrets)
    
*   Run locally only
    

Nothing else.