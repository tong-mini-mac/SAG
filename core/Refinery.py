import os
import shutil
import json
from .Utils import LLMInterface, extract_json, CONFIG

class DataRefinery:
    def __init__(self, vault_path=None):
        self.vault_path = vault_path or CONFIG["CLEANED_DATA_PATH"]
        self.registry_file = os.path.join(os.path.dirname(__file__), "..", "workspace", "registry_counters.json")
        self.org_config_file = os.path.join(os.path.dirname(__file__), "..", "config", "org_structure.json")
        os.makedirs(os.path.dirname(self.registry_file), exist_ok=True)
        os.makedirs(self.vault_path, exist_ok=True)

    @property
    def ai(self):
        """Always resolve latest keys from Streamlit session / config (trial PnP)."""
        return LLMInterface.get_client()

    def _load_org_config(self):
        if os.path.exists(self.org_config_file):
            with open(self.org_config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"departments": []}

    def _get_next_id(self, dept_code):
        """Generates the next document ID for a department."""
        counters = {}
        if os.path.exists(self.registry_file):
            with open(self.registry_file, 'r') as f:
                counters = json.load(f)
        
        current = counters.get(dept_code, 0) + 1
        counters[dept_code] = current
        
        with open(self.registry_file, 'w') as f:
            json.dump(counters, f, indent=4)
        
        return f"{dept_code}-{current:03d}"

    def refine_content(self, raw_text, original_filename, department="General"):
        """The 'Registrar Bot' logic: Categorizes, Names, and Codes the document."""
        org_config = self._load_org_config()
        dept_list = [d["name"] for d in org_config["departments"]]
        
        system_instruction = f"""
        You are the 'RAG-Destroyer Registrar Bot'. 
        Your mission is to register raw data into the vault with perfect categorization and coding.
        
        1. CLASSIFY DEPT: Determine which department this belongs to. 
           AUTHORIZED DEPARTMENTS: {', '.join(dept_list)}
        2. SMART NAMING: Suggest a search-friendly ENGLISH filename (without .md extension).
        3. DOC ID: Suggest a 3-letter prefix based on the content or department.
        4. STRUCTURE: Convert to clean Markdown with YAML frontmatter.
           Include fields: title, doc_id, category, department, related_departments, tags, summary.
           ALL fields including title and summary MUST be in English.
           
        Output format:
        {{
            "suggested_filename": "...",
            "target_department": "...",
            "dept_prefix": "...",
            "category": "...",
            "markdown_content": "---yaml\n...\n---\n# Content..."
        }}
        """
        
        prompt = f"Original Filename: {original_filename}\nDepartment: {department}\nRaw Content:\n{raw_text[:8000]}" # Limit to 8k chars for safety
        
        result_raw = self.ai.call(prompt, system_instruction=system_instruction, json_mode=True)
        try:
            data = json.loads(extract_json(result_raw))
            return data
        except Exception as e:
            print(f"Error refining content: {e}")
            return None

    def process_file(self, raw_file_path, department="General"):
        """Processes a single file from raw_data to knowledge/."""
        if not os.path.exists(raw_file_path):
            return False
            
        with open(raw_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw_text = f.read()

        basename = os.path.basename(raw_file_path)
        print(f"💎 Refining: {basename}...")
        
        refined = self.refine_content(raw_text, basename, department)
        
        if refined:
            # Override department with AI's suggestion if available
            final_dept = refined.get("target_department", department)
            
            # Generate Real Doc ID
            prefix = refined.get("dept_prefix", "GEN").upper()
            doc_id = self._get_next_id(prefix)
            
            # Inject final Doc ID and Department into content
            final_content = refined["markdown_content"].replace("doc_id: PENDING", f"doc_id: {doc_id}")
            final_content = final_content.replace(f"department: {department}", f"department: {final_dept}")
            
            if "doc_id:" not in final_content:
                final_content = final_content.replace("---", f"---\ndoc_id: {doc_id}", 1)

            new_filename = f"[{doc_id}] {refined['suggested_filename'].replace('/', '-')}.md"
            dept_path = os.path.join(self.vault_path, final_dept)
            os.makedirs(dept_path, exist_ok=True)
            
            save_path = os.path.join(dept_path, new_filename)
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
            
            print(f"✅ Saved to: {save_path}")
            return True
        return False

    def scan_and_refine_all(self, raw_dir="raw_data", default_dept="General"):
        """Scans raw_dir and processes all files."""
        if not os.path.exists(raw_dir):
            os.makedirs(raw_dir, exist_ok=True)
            print(f"Created {raw_dir}. Please put your raw files there.")
            return

        for filename in os.listdir(raw_dir):
            if filename.startswith("."): continue
            file_path = os.path.join(raw_dir, filename)
            if os.path.isfile(file_path):
                self.process_file(file_path, default_dept)
