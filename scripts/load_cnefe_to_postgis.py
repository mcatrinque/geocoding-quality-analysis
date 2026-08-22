import os
import sys
import time

import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.env import database_url
from src.normalize import normalize_logradouro

# Credenciais vêm do .env (veja .env.example); nada de senha no código.
DB_URL = database_url()


def load_data():
    print("Iniciando carga de dados do CNEFE...")
    start_time = time.time()

    # 1. Leitura do Parquet mestre
    print("1. Lendo arquivo parquet...")
    df = gpd.read_parquet('data/processed/cnefe_master_metrics.parquet')
    print(f"Total de registros originais: {len(df):,}")

    # 2. Reprojeção para EPSG:4326 (WGS84), padrão do PostGIS
    print("2. Reprojetando geometria para EPSG:4326 (WGS84)...")
    df = df.to_crs(epsg=4326)

    # 3. Registro por unidade (antes da deduplicação)
    print("3. Mapeando colunas...")
    rec = gpd.GeoDataFrame(geometry=df.geometry, crs=4326)

    split_logr = df['LOGRAD_NUM'].str.rsplit(',', n=1, expand=True)
    rec['logradouro'] = split_logr[0].str.strip().str.slice(0, 255)
    rec['numero'] = split_logr[1].str.strip().str.slice(0, 50) if split_logr.shape[1] > 1 else None
    no_comma = split_logr[1].isna() if split_logr.shape[1] > 1 else pd.Series(True, index=df.index)
    rec.loc[no_comma, 'logradouro'] = df.loc[no_comma, 'LOGRAD_NUM'].str.strip().str.slice(0, 255)

    # Forma canônica do logradouro. Garante consistência entre fontes; no CNEFE,
    # que já vem por extenso e sem acento, é quase idempotente.
    rec['logradouro'] = rec['logradouro'].map(normalize_logradouro).str.slice(0, 255)

    rec['complemento'] = df['COMPLEMENTO'].str.slice(0, 150) if 'COMPLEMENTO' in df.columns else None
    rec['bairro'] = df['NOME_BAIRR'].str.slice(0, 100) if 'NOME_BAIRR' in df.columns else None
    rec['cep'] = df['CEP'].str.slice(0, 15) if 'CEP' in df.columns else None
    rec['municipio'] = 'Belo Horizonte'
    rec['uf'] = 'MG'
    rec['lci'] = df['LCI'] if 'LCI' in df.columns else None
    rec['mci'] = df['MCI'] if 'MCI' in df.columns else None
    rec['cdi'] = df['cdi'] if 'cdi' in df.columns else None
    rec['gci'] = df['GCI_empirico'] if 'GCI_empirico' in df.columns else None
    rec['id_fonte'] = 1  # CNEFE_2022 (ver init.sql)
    rec['longitude'] = rec.geometry.x
    rec['latitude'] = rec.geometry.y

    # 4. Deduplicação por endereço geocodificável: logradouro + numero + coordenada
    #    (arredondada a ~1e-5 grau, cerca de 1 m). Evita duplicar o ponto nos
    #    edifícios verticais, onde muitas unidades compartilham a coordenada.
    print("4. Deduplicando por endereço geocodificável...")
    kx = rec['longitude'].round(5).astype(str)
    ky = rec['latitude'].round(5).astype(str)
    key = rec['logradouro'].fillna('') + '|' + rec['numero'].fillna('') + '|' + kx + '|' + ky
    rec['id_endereco'] = pd.factorize(key)[0] + 1

    endereco = rec.drop_duplicates('id_endereco', keep='first').set_index('id_endereco')
    endereco['n_unidades'] = rec.groupby('id_endereco').size()
    endereco = endereco.reset_index()
    endereco = endereco[['id_endereco', 'id_fonte', 'logradouro', 'numero', 'bairro', 'cep',
                         'municipio', 'uf', 'lci', 'mci', 'cdi', 'gci', 'n_unidades',
                         'latitude', 'longitude', 'geometry']]
    endereco = gpd.GeoDataFrame(endereco, geometry='geometry', crs=4326).rename_geometry('geom')
    print(f"   {len(rec):,} registros -> {len(endereco):,} endereços únicos "
          f"({len(endereco)/len(rec)*100:.1f}%)")

    # 5. Complementos -> tabela unidade (só onde há complemento)
    tem_comp = rec['complemento'].notna() & (rec['complemento'].astype(str).str.strip() != '')
    unidade = rec.loc[tem_comp, ['id_endereco', 'complemento']].reset_index(drop=True)
    unidade.insert(0, 'id_unidade', range(1, len(unidade) + 1))
    print(f"   Unidades com complemento: {len(unidade):,}")

    # 6. Inserção (idempotente: limpa as tabelas antes de recarregar)
    print("6. Conectando ao PostgreSQL e inserindo...")
    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE endereco, unidade RESTART IDENTITY CASCADE;"))
    endereco.to_postgis('endereco', con=engine, if_exists='append', index=False, chunksize=25000)
    unidade.to_sql('unidade', con=engine, if_exists='append', index=False, chunksize=50000)

    elapsed = time.time() - start_time
    print(f"Carga finalizada com sucesso em {elapsed/60:.2f} minutos.")


if __name__ == '__main__':
    load_data()
