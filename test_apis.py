"""
test_apis.py
Test AWS Bedrock and Pinecone connections before running the app.
Run: python test_apis.py
"""
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("  [WARN] python-dotenv not installed. Run: pip install python-dotenv==1.0.1")

# ── Colours for terminal output ───────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}[PASS]{RESET} {msg}")
def fail(msg): print(f"  {RED}[FAIL]{RESET} {msg}")
def info(msg): print(f"  {BLUE}[INFO]{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}[WARN]{RESET} {msg}")


# ════════════════════════════════════════════════════════════════════════════
# TEST 1: Check .env keys exist
# ════════════════════════════════════════════════════════════════════════════
def test_env_keys():
    print(f"\n{BOLD}Test 1: Checking .env file keys...{RESET}")

    required_keys = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "BEDROCK_LLM_MODEL",
        "BEDROCK_EMBED_MODEL",
        "PINECONE_API_KEY",
        "PINECONE_INDEX_NAME",
    ]

    all_ok = True
    for key in required_keys:
        val = os.getenv(key)
        if val:
            ok(f"{key} = {val[:12]}...")
        else:
            fail(f"{key} is missing in .env")
            all_ok = False

    return all_ok


# ════════════════════════════════════════════════════════════════════════════
# TEST 2: AWS Bedrock — Titan Embeddings
# ════════════════════════════════════════════════════════════════════════════
def test_bedrock_embeddings():
    print(f"\n{BOLD}Test 2: AWS Bedrock — Titan Embeddings...{RESET}")

    try:
        import boto3
        import json

        region   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        model_id = os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-image-v1")

        info(f"Region : {region}")
        info(f"Model  : {model_id}")

        client = boto3.client(
            service_name="bedrock-runtime",
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

        # Titan embed-image-v1 uses inputText key
        body = json.dumps({
            "inputText": "This is a test sentence for embedding a research paper.",
        })

        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        result    = json.loads(response["body"].read())
        embedding = result.get("embedding", [])

        ok(f"Embedding generated successfully")
        ok(f"Embedding dimension: {len(embedding)}")

        if len(embedding) == 1024:
            ok("Dimension matches Pinecone index (1024)")
        else:
            warn(f"Dimension is {len(embedding)} — make sure Pinecone index also uses {len(embedding)}")

        return True, len(embedding)

    except Exception as e:
        fail(f"Bedrock Embeddings failed: {str(e)}")
        if "AccessDenied" in str(e):
            warn("Tip: Attach AmazonBedrockFullAccess policy to your IAM user.")
        elif "ResourceNotFoundException" in str(e):
            warn("Tip: Enable this model in AWS Bedrock > Model access.")
        elif "InvalidSignatureException" in str(e):
            warn("Tip: AWS keys are wrong. Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")
        return False, 0


# ════════════════════════════════════════════════════════════════════════════
# TEST 3: AWS Bedrock — Claude LLM
# ════════════════════════════════════════════════════════════════════════════
def test_bedrock_llm():
    print(f"\n{BOLD}Test 3: AWS Bedrock — Claude LLM...{RESET}")

    try:
        import boto3
        import json

        region   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        model_id = os.getenv("BEDROCK_LLM_MODEL", "global.anthropic.claude-sonnet-4-6")

        info(f"Region : {region}")
        info(f"Model  : {model_id}")

        client = boto3.client(
            service_name="bedrock-runtime",
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 50,
            "temperature": 0.1,
            "messages": [
                {"role": "user", "content": "Say exactly these words: API test successful"}
            ],
        })

        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        reply  = result["content"][0]["text"]

        ok(f"Claude responded: '{reply.strip()}'")
        ok("Claude LLM is working correctly")
        return True

    except Exception as e:
        fail(f"Bedrock LLM failed: {str(e)}")
        if "AccessDenied" in str(e):
            warn("Tip: Enable Claude model in AWS Bedrock > Model access.")
        elif "ResourceNotFoundException" in str(e):
            warn("Tip: Model ID is wrong or not enabled. Check BEDROCK_LLM_MODEL in .env")
        elif "ValidationException" in str(e):
            warn("Tip: Model ID format is wrong. Check BEDROCK_LLM_MODEL in .env")
        return False


# ════════════════════════════════════════════════════════════════════════════
# TEST 4: Pinecone Connection
# ════════════════════════════════════════════════════════════════════════════
def test_pinecone():
    print(f"\n{BOLD}Test 4: Pinecone Vector Database...{RESET}")

    try:
        from pinecone import Pinecone

        api_key    = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME", "paper-comparison-engine")

        pc = Pinecone(api_key=api_key)
        info(f"Connecting to index: {index_name}")

        existing = [idx.name for idx in pc.list_indexes()]
        info(f"All your indexes: {existing}")

        if index_name not in existing:
            fail(f"Index '{index_name}' not found!")
            warn(f"Create index named '{index_name}' on pinecone.io dashboard.")
            return False, 0

        ok(f"Index '{index_name}' found!")
        index = pc.Index(index_name)
        stats = index.describe_index_stats()

        ok(f"Index dimension  : {stats.dimension}")
        ok(f"Total vectors    : {stats.total_vector_count}")
        ok(f"Namespaces       : {list(stats.namespaces.keys()) or 'empty (no papers yet)'}")

        return True, stats.dimension

    except Exception as e:
        fail(f"Pinecone failed: {str(e)}")
        if "Unauthorized" in str(e) or "401" in str(e):
            warn("Tip: PINECONE_API_KEY is wrong. Copy from pinecone.io > API Keys.")
        return False, 0


# ════════════════════════════════════════════════════════════════════════════
# TEST 5: End-to-End (Embed > Store > Retrieve > Cleanup)
# ════════════════════════════════════════════════════════════════════════════
def test_end_to_end(embed_dim: int):
    print(f"\n{BOLD}Test 5: End-to-End (Embed > Store > Retrieve)...{RESET}")

    if embed_dim == 0:
        fail("Skipping — embedding test failed, dimension unknown.")
        return False

    try:
        import boto3
        import json
        from pinecone import Pinecone

        region   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        model_id = os.getenv("BEDROCK_EMBED_MODEL")

        bedrock = boto3.client(
            service_name="bedrock-runtime",
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

        # Step 1: Generate embedding
        test_text = "Retrieval Augmented Generation improves LLM factual accuracy."
        body = json.dumps({"inputText": test_text})

        response  = bedrock.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        embedding = json.loads(response["body"].read())["embedding"]
        ok(f"Step 1: Embedding generated ({len(embedding)} dims)")

        # Step 2: Store in Pinecone test namespace
        pc    = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

        index.upsert(
            vectors=[{
                "id": "test_vector_001",
                "values": embedding,
                "metadata": {"text": test_text, "source": "api_test"}
            }],
            namespace="api_test_namespace"
        )
        ok("Step 2: Vector stored in Pinecone test namespace")

        # Step 3: Query it back
        results = index.query(
            vector=embedding,
            top_k=1,
            namespace="api_test_namespace",
            include_metadata=True,
        )

        if results.matches:
            match = results.matches[0]
            ok(f"Step 3: Retrieved — score: {round(match.score, 4)}")
            ok(f"         Text: '{match.metadata.get('text', '')}'")
        else:
            fail("Step 3: No results returned from Pinecone")
            return False

        # Step 4: Cleanup
        index.delete(delete_all=True, namespace="api_test_namespace")
        ok("Step 4: Test namespace cleaned up")

        return True

    except Exception as e:
        fail(f"End-to-end test failed: {str(e)}")
        return False


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{BOLD}{'='*55}{RESET}")
    print(f"{BOLD}  Scientific Paper Comparison Engine - API Tests{RESET}")
    print(f"{BOLD}{'='*55}{RESET}")

    env_ok                   = test_env_keys()
    embed_ok, embed_dim      = test_bedrock_embeddings()
    llm_ok                   = test_bedrock_llm()
    pinecone_ok, pine_dim    = test_pinecone()
    e2e_ok                   = test_end_to_end(embed_dim)

    # Dimension mismatch warning
    if embed_dim > 0 and pine_dim > 0 and embed_dim != pine_dim:
        print(f"\n  {YELLOW}{BOLD}WARNING: Embedding dim ({embed_dim}) != Pinecone dim ({pine_dim}){RESET}")
        print(f"  {YELLOW}Recreate Pinecone index with dimension {embed_dim}{RESET}")

    results = {
        "ENV Keys"          : env_ok,
        "Bedrock Embeddings": embed_ok,
        "Bedrock LLM"       : llm_ok,
        "Pinecone DB"       : pinecone_ok,
        "End-to-End"        : e2e_ok,
    }

    print(f"\n{BOLD}{'='*55}{RESET}")
    print(f"{BOLD}  FINAL RESULTS{RESET}")
    print(f"{BOLD}{'='*55}{RESET}")

    passed = 0
    for name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {status}  {name}")
        if result:
            passed += 1

    print(f"\n  {BOLD}Score: {passed}/{len(results)} tests passed{RESET}")

    if passed == len(results):
        print(f"\n  {GREEN}{BOLD}All tests passed!")
        print(f"  Run: streamlit run frontend/app.py{RESET}\n")
    else:
        print(f"\n  {YELLOW}Fix the failing tests above then run again.{RESET}\n")