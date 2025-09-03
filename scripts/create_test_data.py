#!/usr/bin/env python3
"""
Create test data files for the compliance kit
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, date
import random

def create_budget_excel_sample():
    """Create sample budget execution data in Excel format"""
    
    # Sample data in English
    data = [
        {
            'Period': '2025-01',
            'Department': 'Education',
            'Budget Line': 'EDU.01',
            'Description': 'Teacher salaries',
            'Planned Amount': 150000.50,
            'Executed Amount': 145230.25,
            'Remaining': 4770.25,
            'Execution %': 96.82,
            'Status': 'active',
            'Responsible': 'John Smith',
            'Currency': 'BGN'
        },
        {
            'Period': '2025-01',
            'Department': 'Healthcare',
            'Budget Line': 'HLT.01',
            'Description': 'Medical supplies',
            'Planned Amount': 75500.00,
            'Executed Amount': 72150.80,
            'Remaining': 3349.20,
            'Execution %': 95.56,
            'Status': 'active',
            'Responsible': 'Dr. Maria Johnson',
            'Currency': 'BGN'
        },
        {
            'Period': '2025-01',
            'Department': 'Transportation',
            'Budget Line': 'TRP.01',
            'Description': 'Road maintenance',
            'Planned Amount': 200000.00,
            'Executed Amount': 185750.30,
            'Remaining': 14249.70,
            'Execution %': 92.88,
            'Status': 'active',
            'Responsible': 'Steve Wilson',
            'Currency': 'BGN'
        },
        {
            'Period': '2025-01',
            'Department': 'Culture',
            'Budget Line': 'CUL.01',
            'Description': 'Cultural events',
            'Planned Amount': 25000.00,
            'Executed Amount': 23800.50,
            'Remaining': 1199.50,
            'Execution %': 95.20,
            'Status': 'active',
            'Responsible': 'Elena Brown',
            'Currency': 'BGN'
        },
        {
            'Period': '2025-01',
            'Department': 'Administration',
            'Budget Line': 'ADM.01',
            'Description': 'Office supplies',
            'Planned Amount': 12500.75,
            'Executed Amount': 11200.00,
            'Remaining': 1300.75,
            'Execution %': 89.59,
            'Status': 'active',
            'Responsible': 'George Miller',
            'Currency': 'BGN'
        },
        {
            'Period': '2025-01',
            'Department': 'Social Services',
            'Budget Line': 'SOC.01',
            'Description': 'Citizen assistance',
            'Planned Amount': 80000.00,
            'Executed Amount': 78500.00,
            'Remaining': 1500.00,
            'Execution %': 98.13,
            'Status': 'active',
            'Responsible': 'Anna Davis',
            'Currency': 'BGN'
        },
        {
            'Period': '2025-01',
            'Department': 'Environment',
            'Budget Line': 'ENV.01',
            'Description': 'City cleaning',
            'Planned Amount': 35000.25,
            'Executed Amount': 34100.15,
            'Remaining': 900.10,
            'Execution %': 97.43,
            'Status': 'active',
            'Responsible': 'Peter Green',
            'Currency': 'BGN'
        },
        {
            'Period': '2025-01',
            'Department': 'Sports',
            'Budget Line': 'SPT.01',
            'Description': 'Sports facilities',
            'Planned Amount': 45200.00,
            'Executed Amount': 42800.75,
            'Remaining': 2399.25,
            'Execution %': 94.69,
            'Status': 'active',
            'Responsible': 'Chris Taylor',
            'Currency': 'BGN'
        }
    ]
    
    df = pd.DataFrame(data)
    return df

def create_messy_budget_data():
    """Create messy budget data to test normalization"""
    
    # Mixed format data with various issues
    data = [
        {
            'Период/Period': '01.2025',  # Different date format
            'Отдел ': 'Образование',    # Extra space
            'Код': 'EDU-01',
            'Описание/Description': 'Заплати учители  ',  # Extra spaces
            'План ': ' 150,000.50 BGN',  # Mixed formatting
            'Факт': '145 230,25',       # European number format
            'Остава': '4,770.25',
            'Статус': 'АКТИВЕН',        # Uppercase
            'Отговорник': 'иван петров' # Lowercase
        },
        {
            'Период/Period': '2025-01-01',
            'Отдел ': 'Healthcare',
            'Код': 'HLT_01',
            'Описание/Description': 'Medical supplies',
            'План ': '75500',
            'Факт': '72.150,80',  # Mixed separators
            'Остава': '3 349.2',
            'Статус': 'Active',
            'Отговорник': 'Dr. Maria Johnson'
        },
        {
            'Период/Period': 'януари 2025',  # Bulgarian month name
            'Отдел ': ' Транспорт ',
            'Код': '',  # Empty field
            'Описание/Description': 'Road maintenance & repairs',
            'План ': '200,000.00 лв.',
            'Факт': '185750.3',
            'Остава': None,  # Null value
            'Статус': 'да',  # Boolean as text
            'Отговорник': 'СТОЯН ДИМИТРОВ'
        }
    ]
    
    df = pd.DataFrame(data)
    return df

def main():
    """Create all test data files"""
    
    # Create directories
    fixtures_dir = Path(__file__).parent.parent / 'tests' / 'data_fixtures'
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    
    print("Creating test data files...")
    
    # Create clean Excel file
    df_clean = create_budget_excel_sample()
    excel_path = fixtures_dir / 'budget_sample_en.xlsx'
    
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df_clean.to_excel(writer, sheet_name='Budget Execution', index=False)
        
        # Add a second sheet with metadata
        metadata = pd.DataFrame([
            ['Organization', 'Sample Municipality'],
            ['Report Period', '2025-01'],
            ['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Total Departments', len(df_clean)],
            ['Total Planned', df_clean['Planned Amount'].sum()],
            ['Total Executed', df_clean['Executed Amount'].sum()],
        ], columns=['Field', 'Value'])
        metadata.to_excel(writer, sheet_name='Metadata', index=False)
    
    print(f"Created: {excel_path}")
    
    # Create messy CSV file for testing normalization
    df_messy = create_messy_budget_data()
    messy_path = fixtures_dir / 'budget_messy_data.csv'
    df_messy.to_csv(messy_path, index=False, encoding='utf-8')
    print(f"Created: {messy_path}")
    
    # Create larger dataset for performance testing
    large_data = []
    departments = ['Education', 'Healthcare', 'Transportation', 'Culture', 'Administration', 
                  'Social Services', 'Environment', 'Sports', 'Infrastructure', 'Security']
    
    for month in range(1, 13):  # 12 months
        for dept in departments:
            for i in range(5):  # 5 budget lines per department
                planned = random.uniform(10000, 200000)
                executed = planned * random.uniform(0.8, 1.1)  # 80-110% execution
                
                large_data.append({
                    'Period': f'2024-{month:02d}',
                    'Department': dept,
                    'Budget Line': f'{dept[:3].upper()}.{i+1:02d}',
                    'Description': f'{dept} - Budget line {i+1}',
                    'Planned Amount': round(planned, 2),
                    'Executed Amount': round(executed, 2),
                    'Remaining': round(planned - executed, 2),
                    'Currency': 'BGN',
                    'Status': random.choice(['active', 'completed', 'cancelled']),
                    'Responsible': f'Manager {random.randint(1, 20)}'
                })
    
    df_large = pd.DataFrame(large_data)
    large_path = fixtures_dir / 'budget_large_dataset.xlsx'
    df_large.to_excel(large_path, index=False, engine='openpyxl')
    print(f"Created: {large_path} ({len(df_large)} rows)")
    
    # Create expected output files (golden files)
    expected_dir = fixtures_dir / 'expected_outputs'
    expected_dir.mkdir(exist_ok=True)
    
    # Clean CSV output
    df_clean_output = df_clean.copy()
    df_clean_output['period'] = df_clean_output['Period']
    df_clean_output['department'] = df_clean_output['Department']
    df_clean_output['budget_line'] = df_clean_output['Budget Line']
    df_clean_output['description'] = df_clean_output['Description']
    df_clean_output['planned_amount'] = df_clean_output['Planned Amount']
    df_clean_output['executed_amount'] = df_clean_output['Executed Amount']
    df_clean_output['remaining_amount'] = df_clean_output['Remaining']
    df_clean_output['execution_percentage'] = df_clean_output['Execution %']
    df_clean_output['status'] = df_clean_output['Status']
    df_clean_output['responsible_person'] = df_clean_output['Responsible']
    df_clean_output['currency'] = df_clean_output['Currency']
    
    # Keep only mapped columns in correct order
    output_columns = [
        'period', 'department', 'budget_line', 'description',
        'planned_amount', 'executed_amount', 'remaining_amount',
        'execution_percentage', 'currency', 'status', 'responsible_person'
    ]
    df_clean_output = df_clean_output[output_columns]
    
    expected_csv = expected_dir / 'budget_sample_en_expected.csv'
    df_clean_output.to_csv(expected_csv, index=False)
    print(f"Created: {expected_csv}")
    
    # Create metadata JSON
    metadata_json = {
        "title": "Municipal Budget Execution Report",
        "description": "Monthly budget execution data for municipal departments",
        "publisher": "Sample Municipality",
        "license": "Open Data License",
        "update_frequency": "monthly",
        "created": datetime.now().isoformat(),
        "modified": datetime.now().isoformat(),
        "temporal_coverage": "2025-01",
        "spatial_coverage": "Sample Municipality",
        "keywords": ["budget", "municipal", "execution", "finance"],
        "format": "CSV",
        "encoding": "UTF-8",
        "column_count": len(output_columns),
        "row_count": len(df_clean_output)
    }
    
    import json
    metadata_path = expected_dir / 'budget_sample_metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata_json, f, indent=2, ensure_ascii=False)
    print(f"Created: {metadata_path}")
    
    print("\nTest data creation completed!")
    print(f"Files created in: {fixtures_dir}")

if __name__ == '__main__':
    main()