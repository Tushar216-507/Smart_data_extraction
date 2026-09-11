import pandas as pd
from pathlib import Path
from typing import List, Dict

class QSFileLoader:
    """
    Loads QS ranking facts directly from official Excel/CSV files instead of scraping.
    Facts generated this way are tagged with provenance: "EXTERNAL_LOADER" and "official_file"
    to satisfy the Project Law assertions.
    """
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"QS File not found: {file_path}")
            
    def load(self, university_name: str) -> List[dict]:
        facts = []
        df = pd.read_excel(self.file_path) if self.file_path.suffix == '.xlsx' else pd.read_csv(self.file_path)
        
        # Look for the university
        match = df[df.apply(lambda row: row.astype(str).str.contains(university_name, case=False).any(), axis=1)]
        
        if not match.empty:
            row = match.iloc[0]
            # Convert columns to facts
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    continue
                    
                field_name = str(col).lower().replace(" ", "_")
                if "rank" in field_name or "score" in field_name:
                    category = "university"
                    subcategory = "statistics"
                else:
                    category = "university"
                    subcategory = "overview"
                    
                facts.append({
                    "category": category,
                    "subcategory": subcategory,
                    "field": field_name,
                    "value": str(val),
                    "confidence": 1.0,
                    "source_url": f"file://{self.file_path.name}",
                    "metadata": {
                        "provenance": "EXTERNAL_LOADER",
                        "source_type": "official_file"
                    }
                })
                
        return facts
