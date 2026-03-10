
import nbformat
nb = nbformat.read('notebooks/04_quality_and_accuracy.ipynb', as_version=4)
found = False
for i, cell in enumerate(nb.cells):
    if 'categoria_analitica' in cell.source:
        print(f"Cell {i} ({cell.cell_type}):")
        print("-" * 20)
        print(cell.source)
        print("-" * 20)
        found = True
if not found:
    print("No occurrences of 'categoria_analitica' found.")
