import json

def patch_notebook(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        patch_code = "import numpy as np\nif not hasattr(np, 'unicode_'):\n    np.unicode_ = np.str_\n"
        
        # Inject at the very first code cell
        for cell in data.get('cells', []):
            if cell.get('cell_type') == 'code':
                source_str = "".join(cell.get('source', []))
                if "np.unicode_" not in source_str:
                    cell['source'] = [patch_code] + cell['source']
                break
                
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        print(f"Successfully patched {filepath}")
    except Exception as e:
        print(f"Failed to patch {filepath}: {e}")

patch_notebook('notebooks/03_completeness_analysis.ipynb')
