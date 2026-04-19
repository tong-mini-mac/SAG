import concurrent.futures
import json
import re
from .Utils import LLMInterface, extract_json, CONFIG, NotificationManager
from .SearchWorker import SearchWorker
import time

# Words too generic for substring search on short corporate summaries
_QUERY_STOPWORDS = frozenset({
    "how", "what", "when", "where", "why", "who", "which", "does", "did", "can", "could",
    "would", "will", "should", "might", "must", "shall", "this", "that", "these", "those",
    "the", "and", "for", "with", "from", "into", "your", "our", "their", "have", "been",
    "there", "here", "also", "only", "just", "about", "please", "tell", "within", "scope",
    "year", "month", "week", "day", "time", "make", "made", "need", "want", "like",
})


def _fallback_keywords_from_query(query: str) -> list[str]:
    """Extract notable English tokens from the user query for literal vault substring search."""
    words = re.findall(r"[A-Za-z]{3,}", (query or "").lower())
    out = []
    for w in words:
        if w in _QUERY_STOPWORDS or w in out:
            continue
        out.append(w)
        if len(out) >= 8:
            break
    return out


class RAGOrchestrator:
    def __init__(self, vault_path=None):
        self.vault_path = vault_path or CONFIG["CLEANED_DATA_PATH"]
        self.ai = LLMInterface.get_client()
        self.worker = SearchWorker(self.vault_path)
        self.notifier = NotificationManager()
        self.max_bots = 2 # Industrial Sweet Spot for API Stability
        self.failure_count = 0

    def generate_keywords(self, query):
        """AI Call 1: Strictly generates keywords from the command to save API costs."""
        system_instruction = """
        You are the 'RAG-Destroyer Semantic Swarm Engine'.
        Your goal is to ensure high RECALL for a deterministic substring search over English policy metadata (titles, tags, summaries).

        1. Analyze the user query (any language).
        2. Output 5-8 search terms as a JSON array of strings.
        3. CRITICAL: Every string MUST be English only — words or short phrases likely to appear in English HR/finance/policy documents.
        4. If the query is Thai, Japanese, or any non-English language, translate the concepts into English terms
           (e.g. Thai asking about welfare/benefits → include "welfare", "benefits", "compensation", "employee", "policy", "allowance").
        5. Include synonyms where helpful (e.g. salary → remuneration, compensation).
        6. Do not output non-Latin script in the JSON array.

        Format: Return a JSON list of strings only.
        """
        raw = self.ai.call(query, system_instruction=system_instruction, json_mode=True)
        try:
            parsed = json.loads(extract_json(raw))
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
            return []
        except Exception:
            return []

    def generate_keywords_multilingual_retry(self, query):
        """Second pass: English-only tokens when the first keyword pass yields no vault hits."""
        system_instruction = """
        The vault stores English Markdown with English titles and summaries only.
        The user may have asked in Thai or another language.

        Return a JSON array of 8-12 English words (single words preferred) that would appear in HR/benefits/welfare policy titles,
        such as: welfare, benefits, compensation, allowance, insurance, leave, payroll, employee, policy, review, annual, bonus, incentive.

        Output JSON array of strings only. No Thai or non-English characters.
        """
        raw = self.ai.call(query, system_instruction=system_instruction, json_mode=True)
        try:
            parsed = json.loads(extract_json(raw))
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
            return []
        except Exception:
            return []

    @staticmethod
    def _resolve_scope_display_name(authorized_scope, actual_subsets):
        """Human-readable scope for prompts and apology lines (fixes list vs string edge cases)."""
        if authorized_scope == "ALL":
            return "the entire organization"
        if isinstance(actual_subsets, list) and len(actual_subsets) == 1:
            return actual_subsets[0]
        if isinstance(actual_subsets, list) and len(actual_subsets) > 1:
            return "the authorized silos (" + ", ".join(actual_subsets) + ")"
        if isinstance(authorized_scope, str) and authorized_scope != "ALL":
            return authorized_scope
        return "your authorized scope"

    def execute_search(self, keywords, allowed_subsets, viewer_role=None, viewer_active_department=None):
        """Spawns parallel search workers for each keyword."""
        all_results = []
        
        # Parallel execution of SearchWorker for each keyword
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_bots) as executor:
            future_to_kw = {
                executor.submit(
                    self.worker.search,
                    kw,
                    allowed_subsets,
                    viewer_role,
                    viewer_active_department,
                ): kw
                for kw in keywords
            }
            for future in concurrent.futures.as_completed(future_to_kw):
                kw = future_to_kw[future]
                try:
                    res = future.result()
                    all_results.append({"keyword": kw, "hits": res})
                except Exception as e:
                    print(f"Worker for '{kw}' failed: {e}")
        
        return all_results

    def calculate_best_subset(self, search_results):
        """
        Calculates the best subset of documents.
        Logic: Documents that appear in multiple keyword searches get higher priority.
        """
        doc_map = {} # path -> {doc_info, count}
        
        for item in search_results:
            for hit in item["hits"]:
                path = hit["path"]
                if path not in doc_map:
                    doc_map[path] = hit
                    doc_map[path]["hit_count"] = 1
                else:
                    # Boost relevance if found by multiple keywords
                    doc_map[path]["relevance"] += hit["relevance"]
                    doc_map[path]["hit_count"] += 1

        # Sort by hit_count (intersections) first, then relevance
        sorted_docs = sorted(doc_map.values(), key=lambda x: (x["hit_count"], x["relevance"]), reverse=True)
        return sorted_docs[:5] # Top 5 documents

    def final_synthesis(self, query, context_docs, scope_name):
        """Final GURU synthesis using authorized expert reasoning."""
        if not context_docs:
            return (
                f"I apologize. Within **{scope_name}**, I could not retrieve any documents whose "
                "title, tags, or summary matched the search terms derived from your question. "
                "Please rephrase using vocabulary that appears in your policies, or confirm the "
                "vault index is up to date (**System Config → Rebuild vault index**)."
            )

        # Prepare context text for token efficiency
        context_text = ""
        for i, doc in enumerate(context_docs):
            try:
                doc_summary = doc.get("summary", "No summary available.")
                content = ""
                with open(doc["path"], 'r', encoding='utf-8') as f:
                    content = f.read()
                    if len(content) > 3000:
                        content = content[:3000] + "... [Content truncated for cost efficiency]"
                
                context_text += f"\n--- SOURCE {i+1}: {doc['title']} (ID: {doc.get('doc_id', 'N/A')}) ---\n"
                context_text += f"DEPARTMENT/SCOPE: {doc.get('department', 'N/A')}\n"
                context_text += f"CONTENT: {content}\n"
            except: continue

        system_instruction = f"""
        You are the 'Global Enterprise GURU' for {scope_name}.
        You are a high-level Senior Executive Advisor who knows every detail within your authorized scope.
        
        GURU Operational Rules:
        1. GLOBAL LANGUAGE: Answer strictly in English with an international professional standard.
        2. SCOPE INTEGRITY: Answer ONLY using the provided source documents. If the answer isn't there, state clearly that it is outside your authorized knowledge.
        3. AUTHORITY: Speak with confidence, wisdom, and professional poise. Do not just summarize; provide actionable 'Executive Insights'.
        4. CITATION: You MUST cite the source ID or Title for every factual claim (e.g., [HRA-001]). Use square brackets.
        5. REASONING: Connect the dots across silos. If Source A mentions a policy and Source B mentions an implementation, explain the synergy.
        6. NO HALLUCINATION: Zero tolerance for guessing. Accuracy is your primary KPI.
        """
        
        prompt = f"Expert Query: {query}\n\nAuthorized Knowledge Context:\n{context_text}"
        
        # Call AI for initial synthesis
        report = self.ai.call(prompt, system_instruction=system_instruction)
        
        # Linguistic Guard: Refine the tone to ensure it meets 'Senior Executive Advisor' standards
        guard_instruction = "Refine the provided response to ensure it sounds like a world-class Senior Executive Advisor. Ensure citations are preserved and the language is polished. Ensure the tone is strictly professional English."
        refined_report = self.ai.call(report, system_instruction=guard_instruction)
        
        return refined_report

    def handle_request(self, query, authorized_scope, viewer_role=None, viewer_active_department=None):
        """Main Pipeline: AI (Keywords) -> Code (Parallel Search/Subset) -> AI (GURU Synthesis)."""
        # Refresh client in case of provider switch in UI
        self.ai = LLMInterface.get_client()
        
        # Determine subsets based on security context (Individual or Department)
        if isinstance(authorized_scope, list) or authorized_scope == "ALL":
            actual_subsets = authorized_scope
        else:
            actual_subsets = [authorized_scope]

        scope_name = self._resolve_scope_display_name(authorized_scope, actual_subsets)

        print(f"🧠 GURU processing: '{query}' within {scope_name}")
        
        # 1. AI Call 1: Generate Keywords — merge with query tokens for substring recall
        keywords = self.generate_keywords(query)
        merged = []
        for k in keywords + _fallback_keywords_from_query(query):
            if isinstance(k, str) and k.strip():
                ks = k.strip()
                if ks.lower() not in [x.lower() for x in merged]:
                    merged.append(ks)
        keywords = merged[:14]

        print(f"🔑 Search Strategy: {keywords}")
        
        # 2. Local Code Execution: Parallel Search (Silo-Restricted)
        search_results = self.execute_search(
            keywords, actual_subsets, viewer_role, viewer_active_department
        )
        
        # 3. Local Code Execution: Expert Subset Selection
        best_context = self.calculate_best_subset(search_results)
        # Thai / multilingual queries: first pass may return nothing — broaden English keywords once
        if not best_context:
            retry_kw = self.generate_keywords_multilingual_retry(query)
            merged2 = []
            for k in keywords + retry_kw + _fallback_keywords_from_query(query):
                if isinstance(k, str) and k.strip():
                    ks = k.strip()
                    if ks.lower() not in [x.lower() for x in merged2]:
                        merged2.append(ks)
            keywords = merged2[:18]
            print(f"🔁 Retry search keywords: {keywords}")
            search_results = self.execute_search(
                keywords, actual_subsets, viewer_role, viewer_active_department
            )
            best_context = self.calculate_best_subset(search_results)

        print(f"📊 GURU found {len(best_context)} key references.")
        
        # 4. AI Call 2: Final GURU Expert Synthesis
        try:
            report = self.final_synthesis(query, best_context, scope_name)
            self.failure_count = 0 # Reset on success
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= 2:
                self.notifier.send_line(f"🛡️ SAFETY CUT: Orchestrator encountered multiple failures. Cool-down activated.")
                return {
                    "answer": "I apologize. The system is currently in cool-down mode to maintain stability. Please try again later.",
                    "sources": [],
                    "keywords": keywords,
                    "guru_scope": scope_name
                }
            raise e
        
        return {
            "answer": report,
            "sources": best_context,
            "keywords": keywords,
            "guru_scope": scope_name
        }
