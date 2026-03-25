import subprocess
import os
from pathlib import Path

def run_notebook(nb_path):
    print(f"Running {nb_path}...")
    try:
        # Using execute-preprocessor to run the notebook and save it in place
        result = subprocess.run([
            "jupyter", "nbconvert", "--to", "notebook", "--execute", 
            "--inplace", "--ExecutePreprocessor.timeout=1200", str(nb_path)
        ], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error running {nb_path}:\n{result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Exception running {nb_path}: {e}")
        return False

def main():
    notebooks = sorted(list(Path("notebooks").glob("*.ipynb")))
    if not notebooks:
        print("No notebooks found in notebooks/ directory.")
        return

    for nb in notebooks:
        success = run_notebook(nb)
        if not success:
            print(f"Pipeline failed at {nb}")
            break
    else:
        print("Pipeline execution completed successfully!")

if __name__ == "__main__":
    main()
