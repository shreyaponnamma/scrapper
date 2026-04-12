import pandas as pd

def deep_audit():
    f_oscar = 'oscar_satellite_data_full_perfection.xlsx'
    f_ceos = 'satellite_data_full.xlsx'
    f_comb = 'combined_satellite_data_strict.xlsx'

    print('Loading files...')
    df_o = pd.read_excel(f_oscar)
    df_c = pd.read_excel(f_ceos)
    df_comb = pd.read_excel(f_comb)

    print(f'Original OSCAR rows: {len(df_o)}')
    print(f'Original CEOS rows:  {len(df_c)}')

    forbidden = ['inactive', 'considered', 'planned', 'lost at launch', 'presumably inactive']
    df_o_f = df_o[~df_o['Sat_Status'].fillna('').str.lower().isin(forbidden)]
    df_c_f = df_c[~df_c['Mission Status'].fillna('').str.lower().isin(forbidden)]

    print(f'\nFiltered OSCAR rows (active/approved): {len(df_o_f)}')
    print(f'Filtered CEOS rows (active/approved):  {len(df_c_f)}')
    print(f'Combined file rows:                    {len(df_comb)}')

    dup_rows = df_comb.duplicated().sum()
    print(f'\nDuplicate identical rows in combined: {dup_rows}')

    dup_cols_names = set([x for x in df_comb.columns if list(df_comb.columns).count(x) > 1])
    print(f'Duplicate column names: {list(dup_cols_names)}')

    bad_cols = [c for c in df_comb.columns if c.endswith('_ceos') or c.endswith('_oscar') or c.endswith('_x') or c.endswith('_y')]
    print(f'Columns with internal merge suffixes left: {bad_cols}')

    o_names = set(df_o_f['Sat_Acronym'].dropna())
    comb_o_names = set(df_comb['Sat_Acronym'].dropna())
    missing_o = o_names - comb_o_names

    c_names = set(df_c_f['Satellite Full Name'].dropna())
    comb_c_names = set(df_comb['Sat_Full_Name'].dropna())
    missing_c = c_names - comb_c_names

    print(f'\nOSCAR items in filtered but not in combined: {len(missing_o)}')
    if missing_o:
        print(f'Sample missing OSCAR: {list(missing_o)[:5]}')

    print(f'CEOS items in filtered but not in combined:  {len(missing_c)}')
    if missing_c:
        print(f'Sample missing CEOS: {list(missing_c)[:5]}')

    if 'Sat_Full_Name' in df_comb.columns and 'Sat_Acronym' in df_comb.columns:
        matched = df_comb.dropna(subset=['Sat_Full_Name', 'Sat_Acronym'])
        print(f'\nRows with BOTH CEOS and OSCAR data matched: {len(matched)}')
    else:
        print('\nCould not check matched rows due to missing essential columns in combined file.')

if __name__ == "__main__":
    deep_audit()
