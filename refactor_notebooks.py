import nbformat as nbf
from pathlib import Path
import re

notebooks_dir = Path('notebooks')

# Mapping of replacements to make the tone more academic
replacements = [
    (r'(?i)\*\*Foco v4\*\*:.*?\n', ''),
    (r'(?i)Já sabemos que ', 'Sabe-se que '),
    (r'(?i)Vamos explorar ', 'Este notebook tem como objetivo explorar '),
    (r'(?i)Vamos introduzir ', 'São introduzidas '),
    (r'(?i)Aqui abordamos ', 'Esta seção aborda '),
    (r'(?i)Aqui medimos ', 'Esta métrica quantifica '),
    (r'(?i)Neste notebook, vamos ', 'Neste notebook, o objetivo é '),
    (r'(?i)Ok, ', ''),
    (r'(?i)Bom, ', ''),
    (r'(?i)Agora ', 'Em seguida, '),
    (r'(?i)Aqui cruzamos ', 'Realiza-se o cruzamento espacial de '),
    (r'(?i)Queremos ver se ', 'Avalia-se se '),
    (r'(?i)Testamos se ', 'Testa-se se '),
    (r'(?i)O que é:', 'Definição e Metodologia:'),
    (r'(?i)O que é isto\?', 'Introdução à Análise'),
    (r'(?i)O que é este agrupamento\?', 'Apresentação:'),
    (r'(?i)Por que\?', 'Justificativa'),
    (r'(?i)O que é\?', 'Fundamentação'),
    (r'(?i)O que é: ', 'Definição: '),
    (r'(?i)O que é\?\n', 'Metodologia:\n'),
    (r'(?i)O que é esta análise\?\n', 'Metodologia da Análise:\n'),
    # Generic v4 removal
    (r'(?i)\(V4\)', ''),
    (r'(?i)V4 ', ''),
]

headers = {
    '01': 'Avaliação Inicial e Ingestão de Dados (CNEFE 2022)',
    '02': 'Matching Espacial e Textual: CNEFE vs BHMap',
    '03': 'Avaliação de Qualidade Lógica e Atributos de Endereço',
    '04': 'Acurácia Posicional e Indicadores de Incerteza',
    '05': 'Segmentação Tipológica da Qualidade de Geocodificação',
    '06': 'A Geografia da Incerteza: Análise Socioespacial',
    '07': 'Síntese Final e Desigualdade Espacial'
}

for nb_file in sorted(notebooks_dir.glob("*.ipynb")):
    nb_id = nb_file.name[:2]
    
    with open(nb_file, 'r', encoding='utf-8') as f:
        nb = nbf.read(f, as_version=4)
        
    for idx, cell in enumerate(nb.cells):
        if cell.cell_type == 'markdown':
            # Apply regex replacements
            for pattern, repl in replacements:
                cell.source = re.sub(pattern, repl, cell.source)
            
            # Format the title cell if it's the very first cell
            if idx == 0:
                # Force specific academic title
                title = headers.get(nb_id, cell.source.split('\n')[0].replace('# ', ''))
                
                # Try to structure it with Introdução and Objetivos if it's the main header
                if 'Introdução' not in cell.source and nb_id != '07':
                    lines = cell.source.split('\n')
                    new_lines = [f"# Notebook {nb_id}: {title}\n"]
                    new_lines.append("## Introdução")
                    
                    for line in lines[1:]:
                        if line.strip():
                            new_lines.append(line)
                            
                    cell.source = '\n'.join(new_lines)
    
    with open(nb_file, 'w', encoding='utf-8') as f:
        nbf.write(nb, f)
    
    print(f"Refatorado: {nb_file.name}")
