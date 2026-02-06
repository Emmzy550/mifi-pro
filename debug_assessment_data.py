
import json
from utils.db import Database
from models.assessment import Assessment

def debug_assessment(id):
    ass = Database.get_assessment(id)
    if not ass:
        print(f"Assessment {id} not found")
        return
    
    data = ass.model_dump()
    print(json.dumps(data, indent=2, default=str))

if __name__ == "__main__":
    debug_assessment('ASMT-CFB52429')
