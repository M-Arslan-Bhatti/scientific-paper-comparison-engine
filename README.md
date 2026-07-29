# Scientific Paper Comparison Engine
### Multi-Document RAG | AWS Bedrock | Pinecone | LangChain | Streamlit

---

## Architecture

```
PDF Upload
   -> unstructured (multimodal parsing: text + tables + structure)
   -> SmartChunker (LangChain RecursiveCharacterTextSplitter, section-aware)
   -> Amazon Titan Embeddings V2 (1024-dim, via Bedrock)
   -> Pinecone (per-paper namespace)
   -> LangChain RAG chains (per-paper retrieval)
   -> Claude 3.5 Sonnet synthesis (via Bedrock)
   -> Streamlit display (4 tabbed categories)
```

**No FastAPI. No separate backend. Everything runs in one Streamlit Python process.**

---

## Requirements

- Python 3.11.9
- AWS account with Bedrock access
- Pinecone account (free tier works)

---

## Setup

### 1. Create virtual environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure .env
```bash
cp .env.example .env
# Fill in your keys in .env
```

### 4. AWS Bedrock setup
1. Create AWS account at https://aws.amazon.com
2. Go to Bedrock > Model access > Enable:
   - Anthropic Claude 3.5 Sonnet (anthropic.claude-3-5-sonnet-20241022-v2:0)
   - Amazon Titan Text Embeddings V2 (amazon.titan-embed-text-v2:0)
3. Create IAM user with AmazonBedrockFullAccess policy
4. Create access key -> add to .env

### 5. Pinecone setup
1. Create account at https://pinecone.io
2. Create index:
   - Name: paper-comparison-engine
   - Dimensions: 1024
   - Metric: cosine
   - Cloud: AWS, Region: us-east-1
3. Copy API key to .env

### 6. Run the app
```bash
python run.py
# or directly:
streamlit run frontend/app.py
```

Open http://localhost:8501

---

## Project Structure

```
spc/
   ingestion/
      pdf_loader.py      unstructured multimodal PDF parser
      chunker.py         LangChain-based smart chunker
   vectorstore/
      pinecone_store.py  Pinecone with per-paper namespaces
   rag/
      embeddings.py      Amazon Titan V2 (LangChain Embeddings)
      bedrock_llm.py     Claude 3.5 Sonnet (LangChain ChatModel)
      chain.py           LangChain LCEL RAG chain per paper
      comparison.py      Multi-paper comparison orchestration
   frontend/
      app.py             Streamlit UI (main entry point)
      components.py      Reusable styled UI components
   config/
      settings.py        Environment variable loader
   tests/
      test_ingestion.py
   run.py                Launch script
   requirements.txt
   .env.example
```

---

## Run Tests
```bash
pytest tests/ -v
```
